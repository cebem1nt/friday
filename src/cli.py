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
        "Let's see… thinking",
        "I'm piecing together an answer",
        "Hold on, let me reason this out",
        "Running that through my head",
        "Give me a beat to think",
        "I'm sorting through the details",
        "Let me come up with a good answer",
        "Hold on a second",
        "Just a little, almost there!",
    ])


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
        thinking_quote = ""
        i = 1

        with Live(Markdown(content), console=console, refresh_per_second=12) as live:
            for chunk_type, chunk in self.fr.reply(prompt):
                if chunk_type == "thinking":
                    if not is_thinking:
                        thinking_quote = random_thinking_quote()
                        self.fr.say(thinking_quote)
                        is_thinking = True

                    content = thinking_quote
                    content += "." * i
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
                thinking_quote = random_thinking_quote()
                self.fr.say(thinking_quote)
                print(f"{thinking_quote}...")
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

    def toggle_voice_prompt(self):
        is_thinking = False

        for chunk_t, _, in self.fr.listen_or_reply():
            if chunk_t == "thinking" and not is_thinking:
                thinking_quote = random_thinking_quote()
                self.fr.say(thinking_quote)
                is_thinking = True
    