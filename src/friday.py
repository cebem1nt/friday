import ollama, sys, os, re, whisper

import numpy as np
import sounddevice as sd

from piper import PiperVoice, SynthesisConfig
from concurrent.futures import ThreadPoolExecutor
from cli import CLI

import config, utils, tools

class Friday:
    max_tool_calls_rounds = 10

    def __init__(
        self, 
        enable_web_search: bool = False
    ):
        self.model = config.model
        self.voice = PiperVoice.load(config.voice_model)
        self.whisper = whisper.load_model(config.whisper_model)

        self._speech_executor = ThreadPoolExecutor(max_workers=1)
        
        self._output_stream = sd.RawOutputStream(
            samplerate=self.voice.config.sample_rate,
            channels=1,
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
                "You can ask questions if it helps to do what user wants or improve preciseness of your response"
                f"Speak in english by default. Date today: {utils.today()}"
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
                "get_all_applications": tools.get_all_applications
                # "find_applications": tools.find_applications,
            }

            self.messages.append({
                "role": "system",
                "content": "Use web_search for current information and web_fetch to read a page when useful. Cite web-result URLs when you use them."
            })

    def transcribe(self, chunks):
        audio = np.concatenate(chunks).flatten()
        result = self.whisper.transcribe(audio, fp16=False)
        return result["text"].strip()

    def ask(self, prompt: str):
        self.messages.append({ "role": "user", "content": prompt})

        for _ in range(self.max_tool_calls_rounds):
            stream = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools.values() if self.tools else None,
                stream=True,
                keep_alive=True
            )

            content = ""
            tool_calls = []

            for chunk in stream:
                message = chunk.message

                if message.content:
                    content += message.content
                    yield "message", message.content

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
                yield "message", '\n'
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

    def say(self, text: str):
        for chunk in self.voice.synthesize(
            text,
            syn_config=SynthesisConfig(length_scale=0.7),
        ):
            self._output_stream.write(chunk.audio_int16_bytes)

    def aloud(self, response_stream):
        buffer = ""

        for text_type, text in response_stream:
            yield text_type, text

            if not text_type != "message":
                continue

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