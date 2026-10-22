from dataclasses import dataclass, field
from typing import Optional

from src.friday.common import db
from src import log, config

def estimate_tokens(messages: list[dict]):
    text = 0
    media = 0

    for message in messages:
        text += len(str(message.get("content", "")))

        if tool_calls := message.get("tool_calls"):
            text += len(str(tool_calls))

        media += 1100 * len(message.get("images", []))
        media += 798 * len(message.get("audio", []))

    return (text // 3) + media


@dataclass
class Turn:
    messages: list[dict] = field(default_factory=list)
    tokens: Optional[int] = None
    is_completed: bool = False

class Memory:
    def __init__(self, context_total: int):
        self.context_used = 0
        self.context_total = context_total
        self.context_reserve = config.get("misc", "context_reserve", int)
        self.context_target = self.context_total - self.context_reserve

        self.keep_recent_turns = config.get("misc", "keep_recent_turns", int)
        
        if self.keep_recent_turns < 0:
            raise ValueError("keep_recent_turns must be >= 0")

        self._system_prompts: list[dict] = []
        self._turns: list[Turn] = []
        self._current_turn: Optional[Turn] = None

    def __store_turn(self, turn: Turn):
        for message in turn.messages:
            role = message["role"]

            if role == "tool":
                continue

            if role == "assistant" and message.get("tool_calls"):
                continue

            db.add_message_entry(message["role"], message["content"])

    def get_messages(self, system_prompts: bool = True):
        if system_prompts:
            out = list(self._system_prompts)
        else:
            out = []
        
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
            self.__store_turn(self._current_turn)
            self.finish_turn()
            self.prune()

    def prune(self):
        completed = len(self._turns)

        if self._current_turn is not None:
            completed -= 1
        
        removable = max(0, completed - self.keep_recent_turns)

        while self.context_used > self.context_target and removable:
            oldest = self._turns[0]

            if not oldest.is_completed:
                break

            self._turns.pop(0)

            # This is an approximation
            self.context_used = max(0, self.context_used - oldest.tokens)
            removable -= 1

            log.info(f"History: pruned oldest turn ≈ {oldest.tokens} tokens")

    def finish_turn(self):
        if self._current_turn is None:
            return

        self._current_turn.tokens = estimate_tokens(self._current_turn.messages)
        self._current_turn.is_completed = True
        self._current_turn = None

    def wipe_context(self, soft: bool = False):
        log.info("Wiping current context")

        if soft:
            self._turns = self._turns[-1:]
            return 
        
        self._turns = []
        self._current_turn = None

    def clean_memory(self):
        """
        Forget current messages history / context
        """
        self.wipe_context(soft=True)

    def unstage_turn(self):
        if self._current_turn is None:
            return

        self._current_turn = None
        self._turns.pop()