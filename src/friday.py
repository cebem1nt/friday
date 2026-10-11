import ollama, os

from cli import CLI
from voice import VoiceProvider

import config, helpers, tools

# TODO we need a more smart message history
# It's going to be a single chat model, i want an sqllite db storing all time conversations
# it will have a tool to search for some things in the history

class Friday(VoiceProvider):
    max_tool_calls_rounds = 10

    def __init__(
        self, 
        enable_web_search: bool = False
    ):
        super().__init__()
        self.model = config.get("ai", "model")
        self._is_speaking = False

        self.tools = {}
        self.messages = [{ 
            "role": "system", 
            "content": (
                "You're friday: local AI assistant. You are serious, simple, but helpfull. You don't treat user as dumb by default. "
                "Be brief, unless necessary. Never use emoji! Answer directly and concisely. Avoid unnecessary analysis. "
                "You're speaking assistant, that means your responses are spoken aloud, Do not use markdown formatting at all! "
                "You can ask questions if it helps to do what user wants or improve preciseness of your response"
                f"Speak in english by default. Date today: {helpers.today()}"
            )
        }]

        if enable_web_search:
            # TODO alternative search providers

            if not os.getenv("OLLAMA_API_KEY"):
                raise AssertionError("OLLAMA_API_KEY should be set in order to use web search")

            self.tools = { 
                "web_search": tools.web_search, 
                "web_fetch": tools.web_fetch, 
                "run_application": tools.run_application,
                "get_all_applications": tools.get_all_applications,
                # "find_applications": tools.find_applications,
            }

            self.messages.append({
                "role": "system",
                "content": "Use web_search for current information and web_fetch to read a page when useful. Cite web-result URLs when you use them."
            })

    def __ask_stream(self, prompt: str):
        self.messages.append({ "role": "user", "content": prompt})

        for _ in range(self.max_tool_calls_rounds):
            stream = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools.values() if self.tools else None,
                stream=True,
                keep_alive=config.get("ai", "keep_alive")
            )

            content = ""
            tool_calls = []

            for chunk in stream:
                message = chunk.message

                if message.content:
                    content += message.content
                    yield "response", message.content

                if message.tool_calls:
                    yield "system", f"Using tool(s): {message.tool_calls}\n"
                    tool_calls.extend(message.tool_calls)

                if message.thinking:
                    yield "thinking", message.thinking

            message = {
                "role": "assistant",
                "content": content,
            }

            if not tool_calls:
                self.messages.append(message)
                yield "response", '\n'
                return
            
            message["tool_calls"] = [{
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
            } for call in tool_calls]

            self.messages.append(message)

            for call in tool_calls:
                name = call.function.name
                function = self.tools.get(name)
                arguments = call.function.arguments

                if function is None:
                    result = f"Unknown tool: {name}"
                else:
                    result = function(**arguments)

                self.messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": str(result),
                })

        # TODO no good
        yield "system", "Stopped, tool-call limit was hit\n"

    def ask(self, prompt: str, aloud=False):
        if aloud:
            # Interrupts previous speaking 
            self.interrupt_speaking()

        for message_type, message_chunk in self.__ask_stream(prompt):
            if aloud and message_type == "response":
                self.speak(message_chunk)
            
            yield message_type, message_chunk
        
        if aloud:
            self.done_speaking()
