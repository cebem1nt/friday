from src import helpers, config
from src.ipc.client import FridayClient

try:
    import readline
except:
    pass

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

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
                audio = future.result()
                prompt = self.fr.transcribe(audio)
                print(f">> {prompt}")
            
            try:
                if HAS_RICH and config.get("misc", "rich_formatting", bool): 
                    self.__ask_rich(prompt)
                else: 
                    self.__ask_no_rich(prompt)
                    
            except (EOFError, KeyboardInterrupt):
                self.fr.interrupt_speaking()
                return
            