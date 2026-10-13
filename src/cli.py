import os, signal, readline, subprocess
from pathlib import Path
from threading import Event

from src import helpers, config
from src.ipc.client import FridayClient

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

RECORDING_PID_FILE = Path.home() / ".local/state/.friday-recording.pid"

class CLI:
    def __init__(self, friday_client: FridayClient):
        self.fr = friday_client

    def __ask_rich(self, prompt: str):
        console = Console()
        content = ""
        
        is_thinking = False
        thinking_quote = ""
        i = 1

        with Live(Markdown(content), console=console, refresh_per_second=12) as live:
            for chunk_type, chunk in self.fr.ask(prompt):
                if chunk_type == "thinking":
                    if not is_thinking:
                        thinking_quote = helpers.random_thinking_quote()
                        self.fr.say(thinking_quote)
                        is_thinking = True

                    content = thinking_quote
                    content += "." * i
                    i = ((i % 4) + 1)
                else:
                    if is_thinking:
                        content = ""
                        is_thinking = False

                    content += chunk
                
                live.update(Markdown(content))

    def __ask_no_rich(self, prompt: str):
        is_thinking = False

        for chunk_type, chunk in self.fr.ask(prompt):
            if chunk_type == "thinking":
                if not is_thinking:
                    print("Thinking...")
                    is_thinking = True
            else:
                print(chunk, flush=True, end='')

    def __recording_worker(self):
        stop_requested = Event()
        signal.signal(signal.SIGUSR1, lambda _, _2: stop_requested.set())
        
        RECORDING_PID_FILE.write_text(str(os.getpid()))
        self.fr.shut_up()

        try:
            future, stop_recording = helpers.record_audio()

            stop_requested.wait()
            stop_recording()

            audio = future.result()
            prompt = self.fr.transcribe(audio)
            
            # Just speak, dont print anything
            is_thinking = False

            for chunk_t, _ in self.fr.ask(prompt):
                if chunk_t == "thinking":
                    if not is_thinking:
                        thinking_quote = helpers.random_thinking_quote()
                        self.fr.say(thinking_quote)
                        is_thinking = True

        finally:
            if RECORDING_PID_FILE.exists() and RECORDING_PID_FILE.read_text().strip() == str(os.getpid()):
                RECORDING_PID_FILE.unlink()

    def chat(self):
        while True:
            try:
                prompt = input(">> ")
            except (EOFError, KeyboardInterrupt):
                return

            if prompt == "/quit":
                return

            if prompt == "/record":
                future, stop_recording = helpers.record_audio()
                input("Recording, press ENTER to stop")
                stop_recording()
                prompt = self.fr.transcribe(future.result())
                print(f">> {prompt}")
            
            try:
                if HAS_RICH and config.get("misc", "rich_formatting", bool): 
                    self.__ask_rich(prompt)
                else: 
                    self.__ask_no_rich(prompt)
                    
            except (EOFError, KeyboardInterrupt):
                self.fr.shut_up()
                return

    def toggle_voice_prompt(self):
        try:
            pid = int(RECORDING_PID_FILE.read_text().strip())
            os.kill(pid, 0)
        except (FileNotFoundError, ValueError, ProcessLookupError):
            pid = None
        except PermissionError:
            pid = int(RECORDING_PID_FILE.read_text().strip())
        
        if pid is not None:
            os.kill(pid, signal.SIGUSR1)
            print("Stopping recording...")
            return

        child_pid = os.fork()

        if child_pid == 0:
            os.setsid()
            print("Recording audio prompt...")
            self.__recording_worker()
            exit(0)
