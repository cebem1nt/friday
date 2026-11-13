from concurrent.futures import ThreadPoolExecutor
from inspect import getmembers, isfunction
from typing import Generator, Optional, Any
from pprint import pformat

from src.friday.voice import Voice
from src.friday.memory import Memory
from src.friday import skills
from src import config, log, shared

import os, ollama, re, threading, psutil

SYSTEM_PROMPT_FILE = os.path.join(shared.FRIDAY_CONFIG_DIR, "system_prompt.md")
EXTRA_CONTEXT_FILE = os.path.join(shared.FRIDAY_CONFIG_DIR, "extra_context.md")

class ModelSpecs:
    def __init__(self, model: str):
        model_info = ollama.show(model)
        capabilities = model_info.capabilities
        log.debug(f"capabilities: {capabilities}")

        self.tools = "tools" in capabilities
        self.vision = "vision" in capabilities
        self.audio = "audio" in capabilities
        self.thinking = "thinking" in capabilities
        self.arch = model_info.modelinfo.get("general.architecture")
        self.max_context_length = model_info.modelinfo.get(f"{self.arch}.context_length")

class Friday(Voice, Memory):
    max_tool_calls_rounds = 100

    def __init__(self):
        log.info("Friday: setting up Friday...")

        self.keep_alive = config.get("ai", "keep_alive")
        self.model = config.get("ai", "model")
        self.specs = ModelSpecs(self.model)
        self.think = config.get("ai", "think", bool)
        self.tools = {}
        self._reply_lock = threading.Lock()

        if not self.specs.thinking:
            log.info("Thinking is not supported by model")
            self.think = None

        required_context_length = config.get("ai", "num_ctx")

        if required_context_length.lower() == "unlimited":
            context_length = self.specs.max_context_length
        else:
            context_length = int(required_context_length)

        with ThreadPoolExecutor(max_workers=3) as executor:
            tasks = [
                lambda : self.__preload_model(),
                lambda : Voice.__init__(self),
                lambda : Memory.__init__(self, context_length)
            ]
            
            futures = [executor.submit(task) for task in tasks]

            for future in futures:
                future.result()

        self.__init_tools()
        self.__init_prompts()

    def __init_tools(self):
        if not self.specs.tools:
            log.warn("Tools aren't supported by the model")
            return

        if not config.get("ai", "use_tools", bool):
            log.info("Tools are disabled")
            return

        from src.friday import tools # Triggers tools re-init too with -r

        self.tools = { 
            name: func
            for name, func in getmembers(tools, isfunction)
                if not name.startswith("__")
        }

        self.tools["clean_memory"] = self.clean_memory 
        self.tools["add_extra_context"] = self.add_extra_context 
        self.tools["get_skill"] = skills.get_skill

        if tools.WEB_SEARCH_PROVIDER != "none":
            log.info("Friday: Web search is enabled")
        
        if not self.specs.vision:
            self.tools.pop("look_at_the_screen")

        if not (self.specs.vision and self.specs.audio):
            self.tools.pop("view_media")

        log.debug(f"tools: {pformat(self.tools, 2, compact=False)}")

    def __init_prompts(self):
        self.wipe_system_prompts()
        self.wipe_persistent_prompts()

        self.add_system_prompt(f"Date today: {shared.today()}")

        system_prompt_file = SYSTEM_PROMPT_FILE
        model_system_prompt_file = os.path.join(shared.FRIDAY_CONFIG_DIR, self.model + '.md')

        if os.path.exists(model_system_prompt_file):
            system_prompt_file = model_system_prompt_file

        with open(system_prompt_file) as f:
            content = f.read()
            
            if not content:
                log.fatal("System prompt can not be empty!")

            self.add_system_prompt(content)

        if skills_list := skills.discover():
            skill_bullets = "\n".join(f"- Name: {skill.name} - {skill.description}" for skill in skills_list)

            skill_prompt = f"""
            # Skill selection

            Before answering the user, check whether any installed skill matches the request.
            If skill matches:

            1. Load it by calling the tool `get_skill` and passing the skill's exact name as its argument.
            2. Do not call the skill name itself as a tool. For example, if the skill is named `good-morning`, call `get_skill` with `good-morning`; do not call a tool named `good-morning`.
            3. Read and follow the instructions returned by `get_skill`, including any additional required tool calls.
            4. If loading the skill fails, do not retry by calling the skill name as a tool. Continue using the instructions available to you, and do not claim the skill was loaded or its actions completed.

            If no skill is relevant, respond normally. Do not load a skill merely because its name resembles something in the user's message.

            ## Installed skills
            
            {skill_bullets}
            """

            self.add_system_prompt(skill_prompt.strip())

        if os.path.exists(EXTRA_CONTEXT_FILE):
            with open(EXTRA_CONTEXT_FILE) as f:
                if content := f.read():
                    self.add_persistent_prompt(content, "assistant")

    def __preload_model(self):
        if not config.get("ai", "preload", bool):
            return

        if self.model.endswith("cloud"): # No need to pre-load cloud model
            return

        # If battery is not charging, we don't do that.
        if not psutil.sensors_battery().power_plugged: 
            return

        models = { m.name for m in ollama.ps().models }

        if not self.model in models:
            log.info(f"Pre-loading {self.model}")

            # Dummy request to the model
            ollama.chat(
                model=self.model,
                messages=[],
                think=False if self.specs.thinking else None,
                keep_alive=self.keep_alive
            )

    def __reply_call_tools(self, tool_calls: list[dict]):
        for call in tool_calls:
            log.debug(f"__stream_reply_call_tools: tool_call -> {call}")

            name = call["function"]["name"]
            args = call["function"]["arguments"]

            function = self.tools.get(name)

            if function is None:
                result = f"Unknown tool: {name}"
            else:
                result = function(**args)

            log.debug(f"tool response -> {result}")

            if result is None: # If function did not return anything
                result = "Sucess"

            if isinstance(result, str):
                self.add_message(result, role="tool", tool_name=name)
            else:
                self.add_message(
                    result["content"], 
                    role="tool", 
                    images=result.get("images"),
                    audio=result.get("audio"),
                    tool_name=name
                )                        
        

    def __reply(
        self, 
        prompt: str,
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None,
        model: Optional[str] = None,
        think: Optional[bool] = None
    ):
        previous_model = None

        if model is not None:
            previous_model = self.model
            self.set_model(model)      

        if think is None:
            think = self.think

        if not self.specs.vision: images = None
        if not self.specs.audio: audio = None
            
        self.add_message(prompt, images=images, audio=audio)
        log.debug(f"__reply: got message -> {prompt}")

        for _ in range(self.max_tool_calls_rounds):
            self.prune_context()

            stream = ollama.chat(
                stream=True,
                model=self.model,
                messages=self.get_messages(),
                think=think if self.specs.thinking else None,
                tools=self.tools.values() if self.tools else None,
                keep_alive=config.get("ai", "keep_alive"),
                options={ "num_ctx": self.context_total }
            )

            log_thinking = config.get("misc", "log_thinking", bool)
            full_reply = ""
            full_thinking = ""
            tool_calls = []

            try: 
                for chunk in stream:
                    msg = chunk.message

                    if chunk.done:
                        self.update_context_used(chunk.prompt_eval_count + chunk.eval_count)

                    if msg.content:
                        full_reply += msg.content
                        yield "response", msg.content

                    if msg.tool_calls:
                        yield "system", f"Using tool(s): {msg.tool_calls}\n"
                        tool_calls.extend([{
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments
                            }
                        } for call in msg.tool_calls])

                    if msg.thinking:
                        if log_thinking:
                            full_thinking += msg.thinking
                            
                        yield "thinking", msg.thinking

                if not tool_calls:
                    self.add_message(full_reply, role="assistant", finish_turn=True)

                    if log_thinking and full_thinking:
                        log.raw('\nThinking log:\n' + full_thinking + '\n')
                        
                    return full_reply
                
                self.add_message(full_reply, role="assistant", tool_calls=tool_calls)
                self.__reply_call_tools(tool_calls)

            except ollama.ResponseError as e:
                # So, this is a big workaround, for our rolling single chat aproach
                # if ollama throws an error: no "context size left", it looks like this: 
                #   request (4161 tokens) exceeds the available context size (4096 tokens), try increasing it (status code: 400) 
                # We aint afraid of that, we ball and parse it, update self.context_used with that and
                # on the next iteration self.prune_context() will do it's thing

                match = re.search(r"\((\d+)\s+tokens\)", e.error)

                if e.status_code != 400 or not match:
                    raise

                log.debug("got ollama.ResponseError, tokens size exceeded, update self.context_used")
                self.update_context_used(int(match.group(1)))
                continue

            finally:
                if previous_model is not None:
                    self.set_model(previous_model)

        self.add_message("I couldn't finish because the tool-call limit was reached.", role="assistant", finish_turn=True)
        yield "system", "Stopped, tool-call limit was hit"

    def reply(
        self, 
        prompt: str, 
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None,
        model: Optional[str] = None,
        think: Optional[bool] = None,
        stream: bool = True,
        silent: bool = False,
        one_shot: bool = False,
        notify_content: bool = False,
        say_thinking_quote: bool = True
    ) -> Generator[tuple[str, str]] | str:
        
        generation = self.get_generation()
        self.shut_up()

        def generator():
            memory_snapshot = None

            if one_shot:
                memory_snapshot = self.wipe_context()

            try:
                with self._reply_lock:
                    is_thinking = False
                    output = ""

                    for chunk_t, chunk in self.__reply(prompt, images, audio, model, think):
                        if chunk_t == "thinking" and not is_thinking:
                            if not silent and say_thinking_quote and config.get("misc", "enable_thinking_quotes", bool):
                                self.say(shared.random_thinking_quote())
                            is_thinking = True

                        if chunk_t == "response":
                            if not silent:
                                self.speak(chunk, generation)
                            output += chunk

                        yield chunk_t, chunk

                    self.done_speaking(generation)
                    log.debug(f"context used: {self.context_used}/{self.context_total}")
                    
                    if notify_content:
                        shared.notify("Reply from friday", output)
                    
                    return output
            finally:
                if memory_snapshot is not None:
                    self.restore_context(memory_snapshot)

        gen = generator()

        if stream:
            return gen

        while True:
            try:
                next(gen)

            except StopIteration as result:
                return result.value

    def converse(self, stream: bool = True) -> Generator[tuple[str, str]] | Optional[str]:
        if not self.is_listening():
            self.shut_up()
            self.listen()
            shared.notify("Friday is listening", "Press again when done", True)
            return None

        shared.notify("Friday is done listening", "Transcribing your audio...", True)
        prompt = self.done_listening()
        
        if not prompt:
            shared.notify("Looks empty", "You didn't say anything, that's fine.")

        shared.notify("Friday is thinking", f'"{prompt}" - Got it, preparing a response', True)
        return self.reply(prompt, stream=stream, notify_content=True)

    def add_extra_context(self, context: str):
        if not os.path.exists(EXTRA_CONTEXT_FILE):
            with open(EXTRA_CONTEXT_FILE, "w") as f:
                f.write("# Extra context\n\n")

        with open(EXTRA_CONTEXT_FILE, "a") as f:
            f.write("- " + context + '\n')

        if self.persistent_prompts:
            self.persistent_prompts.pop()

        with open(EXTRA_CONTEXT_FILE) as f:
            if content := f.read():
                self.add_persistent_prompt(content)

        return "Context file was updated"

    def set_model(self, model: str):
        log.info(f"Setting model to {model}")
        self.model = model
        self.specs = ModelSpecs(model)
        self.__init_tools()
        self.__init_prompts()

    def idle_actions(self):
        self.kokoro.unload_if_idle()
        self.whisper.unload_if_idle()