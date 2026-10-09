import ollama, sys, os, re, asyncio

import numpy as np
import sounddevice as sd

from piper import PiperVoice, SynthesisConfig
from concurrent.futures import ThreadPoolExecutor

from datetime import datetime
from cli import CLI
# from gui import run_friday_layer

def today():
    return datetime.today().strftime('%Y-%m-%d')

class Friday:
    max_tool_calls_rounds = 10

    def __init__(
        self, 
        enable_web_search: bool = False
    ):
        # self.model = "qwen3.5:9b-q4_K_M"
        self.model = "gemma4:e4b"

        self.voice = PiperVoice.load("/home/cebem1nt/voices/en_US-ljspeech-high.onnx")
        self._speech_executor = ThreadPoolExecutor(max_workers=1)
        
        self._output_stream = sd.RawOutputStream(
            samplerate=self.voice.config.sample_rate,
            channels=1,       # Piper voice output is mono
            dtype="int16",
        )

        self._output_stream.start()
        
        self.tools = {}
        self.messages = [{ 
            "role": "system", 
            "content": (
                "You're friday: local AI assistant. You are serious, simple, but helpfull. You don't treat user as dumb by default. "
                "Be brief, unless necessary. Never use emoji! Answer directly and concisely. Avoid unnecessary analysis. "
                "You're speaking assistant, that means your responses are spoken aloud, Do not use markdown formatting at all! "
                f"Speak in english by default. Date today: {today()}"
            )
        }]

        if enable_web_search:
            # TODO alternative search providers

            if not os.getenv("OLLAMA_API_KEY"):
                raise AssertionError("OLLAMA_API_KEY should be set in order to use web search")

            self.tools = { "web_search": ollama.web_search, "web_fetch": ollama.web_fetch }

            self.messages.append({
                "role": "system",
                "content": "Use web_search for current information and web_fetch to read a page when useful. Cite web-result URLs when you use them."
            })

    def ask(self, prompt: str):
        self.messages.append({ "role": "user", "content": prompt})

        for _ in range(self.max_tool_calls_rounds):
            stream = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools.values() if self.tools else None,
                stream=True
            )

            content = ""
            tool_calls = []

            for chunk in stream:
                message = chunk.message

                if message.content:
                    content += message.content
                    yield message.content

                if message.tool_calls:
                    tool_calls.extend(message.tool_calls)

            message = {
                "role": "assistant",
                "content": content,
            }

            if not tool_calls:
                self.messages.append(message)
                yield '\n'
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
        yield "Stopped, tool-call limit was hit"

    def say(self, text: str):
        # print(f"\nDEBUG: {text}\n")
        for chunk in self.voice.synthesize(
            text,
            syn_config=SynthesisConfig(length_scale=0.7),
        ):
            self._output_stream.write(chunk.audio_int16_bytes)

    def speak(self, text_stream):
        buffer = ""

        for text in text_stream:
            yield text
            buffer += text

            while match := re.search(r"[.!?](?:\s|$)", buffer):
                sentence = buffer[:match.end()].strip()
                buffer = buffer[match.end():]

                if sentence:
                    self._speech_executor.submit(self.say, sentence)

        if buffer.strip():
            self._speech_executor.submit(self.say, buffer.strip())

    def close(self):
        self._speech_executor.shutdown(wait=True)
        self._output_stream.stop()
        self._output_stream.close()

if __name__ == "__main__":
    fr = Friday(enable_web_search=True)
    c = CLI(fr)
    c.chat()

    print(fr.messages)