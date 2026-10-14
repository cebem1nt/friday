import os, readline, random, sys, termios

from src import config
from src.ipc.client import FridayClient
from contextlib import contextmanager

try:
    if not config.get("misc", "rich_formatting", bool):
        raise ImportError

    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    
    USE_RICH = True
except ImportError:
    USE_RICH = False

@contextmanager
def no_stdin_echo():
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    new_attrs = old_attrs.copy()
    new_attrs[3] &= ~termios.ECHO

    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new_attrs)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

class CLI:
    def __init__(self, friday_client: FridayClient):
        self.fr = friday_client

    def __ask_rich(self, prompt: str):
        console = Console()
        content = ""
        
        is_thinking = False
        i = 1

        with Live(Markdown(content), console=console, refresh_per_second=12) as live:
            for chunk_type, chunk in self.fr.reply(prompt):
                if chunk_type == "thinking":
                    is_thinking = True
                    content = "Thinking" + ('.' * i)
                    i = ((i + 1) % 4)
                else:
                    if is_thinking:
                        content = ""
                        is_thinking = False

                    content += chunk
                
                live.update(Markdown(content))

    def __ask_no_rich(self, prompt: str):
        is_thinking = False

        for chunk_type, chunk in self.fr.reply(prompt):
            if chunk_type == "thinking" and not is_thinking:
                print("Thinking...")
                is_thinking = True
            else:
                print(chunk, flush=True, end='')

    def chat(self):
        while True:
            try:
                prompt = input(">> ")
            except (EOFError, KeyboardInterrupt):
                return

            if prompt == "/quit":
                return

            if prompt == "/record":
                self.fr.listen()
                input("Recording, press ENTER to stop")
                prompt = self.fr.done_listening()
                print(f">> {prompt}")

            try:
                with no_stdin_echo():
                    if USE_RICH: self.__ask_rich(prompt)
                    else: self.__ask_no_rich(prompt)
                        
            except (EOFError, KeyboardInterrupt):
                self.fr.shut_up()
                return