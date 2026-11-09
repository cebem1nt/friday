from concurrent.futures import ThreadPoolExecutor
from inspect import getmembers, isfunction
from typing import Generator, Optional
from pprint import pformat

from src.friday.voice import Voice
from src.friday.memory import Memory
from src import config, log, shared

import os, ollama, re, threading, psutil

SYSTEM_PROMPT_FILE = os.path.expanduser("~/.config/friday/system_prompt.md")
EXTRA_CONTEXT_FILE = os.path.expanduser("~/.config/friday/extra_context.md")

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
        self.tools = {}
        self.think = config.get("ai", "think", bool)
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

        self.add_system_prompt(f"Date today: {shared.today()}")

        with open(SYSTEM_PROMPT_FILE) as f:
            self.add_system_prompt(f.read())

        if config.get("ai", "use_tools", bool) and self.specs.tools:
            from src.friday import tools # Triggers tools re-init too with -r

            self.tools = { 
                name: func
                for name, func in getmembers(tools, isfunction)
                    if not name.startswith("__")
            }

            self.tools["clean_memory"] = self.clean_memory 
            self.tools["add_extra_context"] = self.add_extra_context 

            if config.get("misc", "web_search_provider") == "none":
                self.tools.pop("web_search")
                self.tools.pop("web_fetch")
            else:
                log.info("Friday: Web search is enabled")
                
            log.debug(f"tools: {pformat(self.tools, 2, compact=False)}")

        elif not self.specs.tools:
            log.warn("Tools aren't supported by the model")

        # This one must be added as the latest prompt
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

    def __stream_reply(
        self, 
        prompt: str,
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None,
        model: Optional[str] = None
    ):
        if not self.specs.vision:
            images = None
            
        if not self.specs.audio:
            audio = None

        self.add_message(prompt, images=images, audio=audio)
        log.debug(f"__stream_reply: got message -> {prompt}")
        
        if not model:
            model = self.model

        for _ in range(self.max_tool_calls_rounds):
            self.prune()

            stream = ollama.chat(
                stream=True,
                model=model,
                messages=self.get_messages(),
                think=self.think,
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
                        self.context_used = chunk.prompt_eval_count + chunk.eval_count

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

                for call in tool_calls:
                    log.debug(f"__stream_reply: tool_call -> {call}")

                    name = call["function"]["name"]
                    arguments = call["function"]["arguments"]
                    function = self.tools.get(name)

                    if function is None:
                        result = f"Unknown tool: {name}"
                    else:
                        result = function(**arguments)

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

            except ollama.ResponseError as e:
                # So, this is a big workaround, for our shitty rolling single chat aproach
                # if ollama throws an error, sayn no "context size left", it looks like this: 
                #   request (4161 tokens) exceeds the available context size (4096 tokens), try increasing it (status code: 400) 
                # We aint afraid of that, we ball and parse it, update self.context_used with that and
                # on the next iteration self.prune() will do it's thing

                match = re.search(r"\((\d+)\s+tokens\)", e.error)

                if e.status_code != 400 or not match:
                    raise

                log.debug("got ollama.ResponseError, tokens size exceeded, update self.context_used")
                self.context_used = int(match.group(1))
                continue

        self.add_message("I couldn't finish because the tool-call limit was reached.", role="assistant", finish_turn=True)
        yield "system", "Stopped, tool-call limit was hit"

    def reply(
        self, 
        prompt: str, 
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None,
        stream: bool = True,
        notify_content: bool = False,
        say_thinking_quote: bool = True,
        silent: bool = False,
        model: Optional[str] = None
    ) -> Generator[tuple[str, str]] | str:
        self.shut_up()
        generation = self.get_generation()

        def generator():
            with self._reply_lock:
                is_thinking = False
                output = ""

                for chunk_t, chunk in self.__stream_reply(prompt, images, audio, model):
                    if chunk_t == "thinking" and not is_thinking:
                        if not silent and say_thinking_quote:
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

        gen = generator()

        if stream:
            return gen

        while True:
            try:
                next(gen)

            except StopIteration as result:
                return result.value

    def converse(
        self, 
        stream: bool = True
    ) -> Generator[tuple[str, str]] | Optional[str]:
        if not self.is_listening():
            self.shut_up()
            self.listen()
            shared.notify("Friday is listening", "Press again when done", True)
            return None

        shared.notify("Friday is done listening", "Transcribing your audio...", True)
        prompt = self.done_listening()
        
        if prompt:
            shared.notify("Friday is thinking", f'"{prompt}" - Got it, preparing a response', True)
            return self.reply(prompt, stream=stream, notify_content=True)

    def idle_actions(self):
        self.kokoro.unload_if_idle()
        self.whisper.unload_if_idle()

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