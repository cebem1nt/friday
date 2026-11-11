from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from contextlib import contextmanager
from src import config
from src.ipc.client import FridayClient
from src.shared import friday_server_is_running

import os, readline, random, sys, termios

def printmd(content: str):
    Console().print(Markdown(content))

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

    def ask(self, prompt: str):
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

    def chat(self):
        if not friday_server_is_running():
            return print("Friday server is not running", file=sys.stderr)

        messages = self.fr.get_messages()

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "user":
                print(f">> {content}")
                continue

            printmd(content)

        while True:
            try:
                prompt = input(">> ")

            except (EOFError, KeyboardInterrupt):
                return

            if prompt.startswith("/"):
                if prompt == "/help":
                    print("/quit    -> quit chat")
                    print("/record  -> record audio prompt")
                    continue
                
                if prompt == "/quit" or prompt == "/exit":
                    return

                elif prompt == "/record":
                    self.fr.listen()
                    input("Recording, press ENTER to stop")
                    prompt = self.fr.done_listening()
                    print(f">> {prompt}")

                else:
                    print("Invalid command. Use /help to see available")
                    continue

            try:
                with no_stdin_echo():
                    self.ask(prompt)
                        
            except (EOFError, KeyboardInterrupt):
                self.fr.shut_up()
                return