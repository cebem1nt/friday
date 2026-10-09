
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

        with Live(Markdown(content), console=console, refresh_per_second=12) as live:
            for chunk in self.fr.ask(prompt):
                content += chunk
                live.update(Markdown(content))

    def __ask_no_rich(self, prompt: str):
        for chunk in self.fr.ask(prompt):
            print(chunk, flush=True, end='')
        

    def chat(self):
        while True:
            prompt = input(">> ")
            
            if HAS_RICH: 
                self.__ask_rich(prompt)
            else: 
                self.__ask_no_rich(prompt)

            