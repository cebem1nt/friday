from typing import Optional
from dataclasses import dataclass, field

from src import log

def should_archive(message: dict):
    role = message["role"]

    if role == "tool":
        return False

    if role == "assistant" and message.get("tool_calls"):
        return False 

    return True

@dataclass
class Turn:
    messages: list[dict] = field(default_factory=list)
    is_completed: bool = False

class History:
    def __init__(self, context_total: int, context_reserve: int = 1500, keep_recent_turns: int = 3):
        self.context_total = context_total
        self.context_reserve = context_reserve
        self.keep_recent_turns = keep_recent_turns

        self._system_prompts = []
        self._turns = [] 
        self._current_turn = None

        # self._messages = []

    @property
    def messages(self):
        out = list(self._system_prompts)
        
        for turn in self._turns:
            out.extend(turn.messages)

        return out

    def add_system_prompt(self, content: str):
        self._system_prompts.append({
            "role": "system",
            "content": content
        })

    def add_message(
        self,
        content: str,
        role="user",
        images: Optional[list[str]] = None,
        audio: Optional[list[str]] = None,
        **extra
    ):
        if role == "user":
            if self._current_turn is not None:
                raise RuntimeError("The previous turn was not finished")

            self._current_turn = Turn()
            self._turns.append(self._current_turn)

        if self._current_turn is None or self._current_turn.is_completed:
            raise RuntimeError("Add a user message to start a turn.")

        message = {
            "role": role,
            "content": content,
            **extra
        }

        if images:
            message["images"] = images
        if audio:
            message["audio"] = audio

        self._current_turn.messages.append(message)

    def finish_turn(self):
        if self._current_turn is not None:
            self._current_turn.is_completed = True
            self._current_turn = None

    def prune(self):
        target_tokens = max(0, self.context_total - self.context_reserve)

        while estimate_tokens(self.messages) > target_tokens:
            eligible_turns = self._turns[:-self.keep_recent_turns]
            
            if not eligible_turns:
                break

            oldest = eligible_turns[0]

            if not oldest.is_completed:
                break

            for message in oldest.messages:
                log.info(f"History: displacing message -> {message}")

                if should_archive(message):
                    log.info(f"History: archiving message")
                    pass # TODO create sql archiving

            self._turns.remove(oldest)
