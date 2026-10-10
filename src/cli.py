import utils, config

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    HAS_RICH = True
except (ImportError):
    HAS_RICH = False

class CLI:
    def __init__(self, friday):
        self.fr = friday

    def __ask_rich(self, prompt: str):
        console = Console()
        content = ""
        
        is_thinking = False
        i = 1

        with Live(Markdown(content), console=console, refresh_per_second=12) as live:
            for chunk_type, chunk in self.fr.aloud(self.fr.ask(prompt)):
                if chunk_type == "thinking":
                    if not is_thinking:
                        is_thinking = True

                    content = "Thinking"
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

        for chunk_type, chunk in self.fr.aloud(self.fr.ask(prompt)):
            if chunk_type == "thinking":
                if not is_thinking:
                    print("Thinking...")
                    is_thinking = True
            else:
                print(chunk, flush=True, end='')
        
    def chat(self):
        while True:
            prompt = input(">> ")

            if prompt == "/quit":
                return

            if prompt == "/record":
                chunks = []

                with utils.record_audio(
                    callback=lambda indata, _, _1, _2: chunks.append(indata.copy())
                ):
                    input("Recording, press ENTER to stop")

                prompt = self.fr.transcribe(chunks)
                print(f">> {prompt}")

            if HAS_RICH and config.rich_formatting: 
                self.__ask_rich(prompt)
            else: 
                self.__ask_no_rich(prompt)

            