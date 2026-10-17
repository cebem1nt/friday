from dataclasses import dataclass, field
from typing import Optional

from src import log

def should_archive(message: dict):
    role = message["role"]

    if role == "tool":
        return False

    if role == "assistant" and message.get("tool_calls"):
        return False 

    return True

def estimate_tokens(messages: list[dict]):
    text = 0
    media = 0

    for message in messages:
        text += len(str(message.get("content", "")))

        if tool_calls := message.get("tool_calls"):
            text += len(str(tool_calls))

        media += 768 * len(message.get("images", []))
        media += 1000 * len(message.get("audio", []))

    return text // 4 + media


@dataclass
class Turn:
    messages: list[dict] = field(default_factory=list)
    tokens: Optional[int] = None
    is_completed: bool = False

class History:
    def __init__(
        self,
        context_total: int,
        context_reserve: int = 1000,
        keep_recent_turns: int = 3,
    ):
        if keep_recent_turns < 0:
            raise ValueError("keep_recent_turns must be >= 0")

        self.context_total = context_total
        self.context_reserve = context_reserve
        self.context_used = 0
        self.context_target = self.context_total - self.context_reserve

        self.keep_recent_turns = keep_recent_turns

        self._system_prompts: list[dict] = []
        self._turns: list[Turn] = []
        self._current_turn: Optional[Turn] = None

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
        role: str = "user",
        images: Optional[list[str]] = None,
        audio: Optional[list[str]] = None,
        finish_turn: bool = False,
        **extra
    ):
        if role == "user":
            if self._current_turn is not None:
                raise RuntimeError("The previous turn was not finished")

            self._current_turn = Turn()
            self._turns.append(self._current_turn)

        if self._current_turn is None:
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

        if finish_turn:
            self.finish_turn()
            self.prune()

    def prune(self):
        completed_count = len(self._turns)

        if self._current_turn is not None:
            completed_count -= 1
        
        removable_count = max(0, completed_count - self.keep_recent_turns)

        while self.context_used > self.context_target and removable_count:
            oldest = self._turns[0]

            if not oldest.is_completed:
                break

            self._archive_turn(oldest)
            self._turns.pop(0)

            self.context_used = max(0, self.context_used - oldest.tokens)
            removable_count -= 1

            log.info(f"History: pruned oldest turn ≈ -{oldest.tokens} tokens")

    def finish_turn(self):
        if self._current_turn is None:
            return

        self._current_turn.tokens = estimate_tokens(self._current_turn.messages)
        self._current_turn.is_completed = True
        self._current_turn = None

    def _archive_turn(self, turn: Turn):
        for message in turn.messages:
            if should_archive(message):
                pass # TODO archive old messages / turns to sql

    def wipe_turns(self, archive: bool = False):
        log.info("Wiping current turns history")

        if archive:
            log.info("Archiving...")
            for turn in self._turns:
                self._archive_turn(turn)
        
        self._turns = []
        self._current_turn = None