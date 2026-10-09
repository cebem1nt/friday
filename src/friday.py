import ollama, sys, os

from datetime import datetime

def today():
    return datetime.today().strftime('%Y-%m-%d')

class Chat:
    max_tool_calls_rounds = 6

    def __init__(
        self, 
        enable_web_search: bool = False
    ):
        self.model = "gemma4:e4b"
        self.tools = {}
        self.messages = [{ 
            "role": "system", 
            "content": (
                "You're friday: local AI assistant. Do not treat user as dumb by default, be serious, simple, but helpfull."
                "Be brief, unless necessary. Never use emoji! Do not use exscessive markdown formatting! Answer directly and concisely. Avoid unnecessary analysis."
                f"Date today: {today()}"
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
                stream=True,
                tools=self.tools.values() if self.tools else None  
            )

            content = ""
            tool_calls = []

            for chunk in stream:
                message = chunk.message

                if message.content:
                    content += message.content
                    print(message.content, flush=True, end='')

                if message.tool_calls:
                    print(f"Using tool(s): {message.tool_calls}")
                    tool_calls.extend(message.tool_calls)

            if not tool_calls:
                print()
                return

            self.messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        }
                    }
                    for call in tool_calls
                ],
            })

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

        print("Stopped, tool-call limit was hit")

    def interactive(self):
        while True:
            prompt = input(">> ")

            if prompt == "/quit":
                return
            
            self.ask(prompt)

if __name__ == "__main__":
    c = Chat(enable_web_search=True)
    c.interactive()

    print(c.messages)