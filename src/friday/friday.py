import os, ollama, random
from inspect import getmembers as igetmembers, isfunction as iisfunction

from datetime import datetime
from typing import Iterable, Optional

from src.friday.voice import VoiceProvider
from src.friday import tools
from src import config, log

# TODO we need a more smart message history
# It's going to be a single chat model, i want an sqllite db storing all time conversations
# it will have a tool to search for some things in the history

def random_thinking_quote():
    return random.choice([
        "Processing your request",
        "I gotta think on a response",
        "Let my brain work a little",
        "Let me think",
        "Let me think about it",
        "I should think about it",
        "I'm thinking",
        "Okay, let me think for a moment",
        "Thinking",
        "I have to think about it",
        "Wait please, I gotta think",
        "Give me a second to think",
        "Let me put my thoughts together",
        "Working through it",
        "One moment while I think",
        "Thinking it through",
        "Let me mull that over",
        "Gathering my thoughts",
        "Hmm, let me think",
        "Just a moment—I'm figuring it out",
        "Let me work this out",
        "Taking a moment to think",
        "My gears are turning",
        "Let's see... thinking",
        "I'm piecing together an answer",
        "Hold on, let me reason this out",
        "Running that through my head",
        "Give me a beat to think",
        "I'm sorting through the details",
        "Let me come up with a good answer",
        "Hold on a second",
    ])

def today():
    return datetime.today().strftime('%Y-%m-%d')

class Friday(VoiceProvider):
    max_tool_calls_rounds = 10

    def __init__(self):
        super().__init__()
        log.info("Friday: setting up Friday...")

        self.model = config.get("ai", "model")
        self.messages = [{ 
            "role": "system", 
            "content": (
                "You're friday: local AI assistant. You are serious, simple, but helpfull. You don't treat user as dumb by default. "
                "Be brief, unless necessary. Never use emoji! Answer directly and concisely. Avoid unnecessary analysis. "
                "You're speaking assistant, that means your responses are spoken aloud, do not use markdown formatting at all! "
                "You can ask questions if it helps to do what user wants or improves preciseness of your response. "
                f"Speak in english by default. Date today: {today()}"
            )
        }]

        self.tools = {}

        if config.get("misc", "enable_web_search", bool):
            # TODO alternative search providers

            log.info("Friday: checking OLLAMA_API_KEY...")
            if not os.getenv("OLLAMA_API_KEY"):
                raise AssertionError("OLLAMA_API_KEY should be set in order to use web search")

            self.tools = { 
                name: func
                for name, func in igetmembers(tools, iisfunction)
                    if not name.startswith("__")
            }

            self.messages.append({
                "role": "system",
                "content": "Use web_search for current information and web_fetch to read a page when useful. Cite web-result URLs when you use them."
            })

    def stream_reply(self, prompt: str):
        self.messages.append({ "role": "user", "content": prompt})
        log.debug(f"stream_reply: got user message -> {prompt}")

        for _ in range(self.max_tool_calls_rounds):
            stream = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools.values() if self.tools else None,
                keep_alive=config.get("ai", "keep_alive"),
                stream=True
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

            log.debug(f"stream_reply: tool_call -> {message}")
            self.messages.append(message)

            for call in tool_calls:
                name = call.function.name
                function = self.tools.get(name)
                arguments = call.function.arguments

                if function is None:
                    result = f"Unknown tool: {name}"
                else:
                    result = function(**arguments)

                log.debug(f"tool response -> {result}")
                message = {
                    "role": "tool",
                    "tool_name": name,
                    "content": result["content"]
                }

                if imgs := result.get("images"):
                    message["images"] = imgs

                if imgs := result.get("audio"):
                    message["audio"] = audio

                self.messages.append(message)

        # TODO no good
        yield "system", "Stopped, tool-call limit was hit\n"

    def reply(self, prompt: str, stream: bool = True) -> Iterable[tuple[str, str]] | str:
        self.shut_up()
        generation = self._generation

        def generator():
            is_thinking = False
            output = ""

            for chunk_t, chunk in self.stream_reply(prompt):
                if chunk_t == "thinking" and not is_thinking:
                    self.say(random_thinking_quote())
                    is_thinking = True

                if chunk_t == "response":
                    self.speak(chunk, generation)
                    output += chunk

                yield chunk_t, chunk

            self.done_speaking()
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
        return self.reply(prompt, stream)