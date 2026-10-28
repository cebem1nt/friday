from typing import Optional

from src.shared import db
from src import log, config

import os, json

CACHE_HOME = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache/"))
FRIDAY_CACHE_DIR = os.path.join(CACHE_HOME, "friday")

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


# @dataclass(slots=True)
# class Turn:
#     messages: list[dict] = field(default_factory=list)
#     tokens: Optional[int] = None
#     is_completed: bool = False

class Memory:
    def __init__(self, context_total: int):
        self.context_used = 0
        self.context_total = context_total
        self.context_reserve = config.get("misc", "context_reserve", int)
        self.context_target = self.context_total - self.context_reserve

        os.makedirs(FRIDAY_CACHE_DIR, exist_ok=True)
        self._turns_file = os.path.join(FRIDAY_CACHE_DIR, ".turns.json")
        
        if not os.path.exists(self._turns_file) or \
            config.get("misc", "wipe_chat_on_daemon_startup", bool):
            with open(self._turns_file, "w") as f:
                json.dump([], f)

        self.turns_length = 0
        self.keep_recent_turns = config.get("misc", "keep_recent_turns", int)
        
        if self.keep_recent_turns < 0:
            raise ValueError("keep_recent_turns must be >= 0")

        self._system_prompts: list[dict] = []
        self._current_turn: Optional[dict] = None

    def __store_turn(self, turn: dict):
        for message in turn["messages"]:
            role = message["role"]

            if role == "tool":
                continue

            if role == "assistant" and message.get("tool_calls"):
                continue

            db.add_message_entry(message["role"], message["content"])

    @property
    def _turns(self) -> list[dict]:
        with open(self._turns_file) as f:
            out = json.load(f)
            self.turns_length = len(out)
            return out

    def __append_turn(self, turn: dict):
        turns = self._turns
        turns.append(turn)
        self.turns_length += 1

        with open(self._turns_file, "w") as f:
            json.dump(turns, f)

    def __shift_turn(self):
        turns = self._turns
        turns.pop(0)
        self.turns_length -= 1

        with open(self._turns_file, "w") as f:
            json.dump(turns, f)

    def get_messages(
        self, 
        system_prompts: bool = True,
        tool_calls: bool = True
    ):
        if system_prompts:
            out = list(self._system_prompts)
        else:
            out = []
        
        for turn in self._turns:
            messages = turn["messages"]

            if not tool_calls:
                not_tool_calls = lambda m: m["role"] != "tool" and (not m.get("tool_calls"))
                messages = filter(not_tool_calls, messages)

            out.extend(messages)

        if self._current_turn is not None:
            out.extend(self._current_turn["messages"])

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

            self._current_turn = {
                "messages": [],
                "tokens": 0,
            }

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

        self._current_turn["messages"].append(message)

        if finish_turn:
            self.finish_turn()
            self.prune()

    def prune(self):        
        removable = max(0, self.turns_length - self.keep_recent_turns)

        while self.context_used > self.context_target and (removable > 0):
            oldest = self._turns[0]

            # This is an approximation
            self.context_used = max(0, self.context_used - oldest["tokens"])

            self.__shift_turn()
            removable -= 1

            log.info(f"History: pruned oldest turn ≈ {oldest["tokens"]} tokens")

    def finish_turn(self):
        if self._current_turn is None:
            return

        finished = self._current_turn
        finished["tokens"] = estimate_tokens(finished["messages"])

        self.__append_turn(finished)
        self.__store_turn(finished)

        self._current_turn = None

    def wipe_context(self, soft: bool = False):
        log.info("Wiping current context")
        
        with open(self._turns_file, "w") as f:
            json.dump([], f)

        if not soft:
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