from typing import Optional

class History:
    def __init__(self, context_total: int):
        self.context_used = 0
        self.context_total = context_total
        self._system_prompts = []
        self._messages = []

    @property
    def messages(self):
        return self._system_prompts + self._messages

    def add_message(
        self,
        content: str,
        role="user",
        images: Optional[list[str]] = None,
        audio: Optional[list[str]] = None,
        **extra
    ):
        message = {
            "role": role,
            "content": content,
            **extra
        }

        if images:
            message["images"] = images
        if audio:
            message["audio"] = audio

        self._messages.append(message)