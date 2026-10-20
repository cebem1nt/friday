from inspect import getmembers as igetmembers, isfunction as iisfunction

from typing import Iterable, Optional

from src.friday.voice import Voice
from src.friday.history import History
from src.friday import tools, common
from src import config, log

import os, ollama, re

SYSTEM_PROMPT = os.path.expanduser("~/.config/friday/system_prompt.md")

class Friday(Voice, History):
    max_tool_calls_rounds = 20

    def __init__(self):
        self.model = config.get("ai", "model")
        self.model_info = ollama.show(self.model)
        self.tools = {}

        arch = self.model_info.modelinfo.get("general.architecture")
        capabilities = self.model_info.capabilities
        self.supports_tools = "tools" in capabilities

        required_context_length = config.get("ai", "num_ctx")

        if required_context_length == "unlimited":
            context_length = self.model_info.modelinfo.get(f"{arch}.context_length")
        else:
            context_length = int(required_context_length)

        Voice.__init__(self)
        History.__init__(self, context_length)

        log.info("Friday: setting up Friday...")

        self.think = config.get("ai", "think", bool)

        if not "think" in capabilities:
            log.info("Thinking is not supported by model")
            self.think = None

        self.add_system_prompt(f"Date today: {common.today()}")

        with open(SYSTEM_PROMPT) as f:
            self.add_system_prompt(f.read())

        if config.get("ai", "use_tools", bool) and self.supports_tools:
            self.tools = { 
                name: func
                for name, func in igetmembers(tools, iisfunction)
                    if not name.startswith("__")
            }

            self.add_system_prompt((
                "Use get_user_selection to get content from clipboard. "
                "User might refer to selected content as \"this\" or \"the selection\". It may return text, a file path, or a URL. \n"

                "Use query_stored_messages to search chat history. "
                "The database contains one table: message(id, timestamp, role, content). Only run read-only queries.\n"

                "You can call more than one tool at once."
            ))

            if config.get("misc", "web_search_provider") == "none":
                self.tools.pop("web_search")
                self.tools.pop("web_fetch")
            else:
                log.info("Friday: Web search is enabled")

                self.add_system_prompt((
                    "Use web_search to search the internet, use web_fetch to get page by **url**. "
                    "Cite web-result URLs when you use them."
                ))
                
            log.debug(f"tools: {self.tools}")

        elif self.supports_tools:
            log.warn("Tools aren't supported by the model")

    def __stream_reply(
        self, 
        prompt: str,
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None
    ):
        self.add_message(prompt, images=images, audio=audio)
        self.prune()
        
        log.debug(f"stream_reply: got user message -> {prompt}")

        for _ in range(self.max_tool_calls_rounds):
            self.prune()

            stream = ollama.chat(
                stream=True,
                model=self.model,
                messages=self.messages,
                tools=self.tools.values() if self.tools else None,
                keep_alive=config.get("ai", "keep_alive"),
                options={"num_ctx": self.context_total}
            )

            full_reply = ""
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
                        yield "thinking", msg.thinking

                if not tool_calls:
                    self.add_message(full_reply, role="assistant", finish_turn=True)
                    return full_reply
                
                self.add_message(full_reply, role="assistant", tool_calls=tool_calls)

                for call in tool_calls:
                    log.debug(f"stream_reply: tool_call -> {call}")

                    name = call["function"]["name"]
                    arguments = call["function"]["arguments"]
                    function = self.tools.get(name)

                    if function is None:
                        result = f"Unknown tool: {name}"
                    else:
                        result = function(**arguments)

                    log.debug(f"tool response -> {result}")

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
        notify_content: bool = False
    ) -> Iterable[tuple[str, str]] | str:
        self.shut_up()
        generation = self._generation

        def generator():
            is_thinking = False
            output = ""

            for chunk_t, chunk in self.__stream_reply(prompt, images, audio):
                if chunk_t == "thinking" and not is_thinking:
                    self.say(common.random_thinking_quote())
                    is_thinking = True

                if chunk_t == "response":
                    self.speak(chunk, generation)
                    output += chunk

                yield chunk_t, chunk

            self.done_speaking()
            log.debug(f"context used: {self.context_used}/{self.context_total}")
            
            if notify_content:
                common.notify("Reply from friday", output)
            
            return output

        gen = generator()

        if stream:
            return gen

        while True:
            try:
                next(gen)

            except StopIteration as result:
                return result.value

    def converse(self, stream: bool = True) -> Iterable[tuple[str, str]] | Optional[str]:
        if not self.is_listening():
            self.shut_up()
            self.listen()
            return None

        prompt = self.done_listening()
        return self.reply(prompt, stream=stream, notify_content=True)