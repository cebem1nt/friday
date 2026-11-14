from typing import Optional

from src.shared import db, FRIDAY_CACHE_DIR
from src import log, config

import os, json

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

class Turns:
    def __init__(self):
        os.makedirs(FRIDAY_CACHE_DIR, exist_ok=True)
        self._file = os.path.join(FRIDAY_CACHE_DIR, "turns.json")
        self.length = 0

        wipe_context = config.get("misc", "wipe_chat_on_daemon_startup", bool)

        if not os.path.exists(self._file) or wipe_context:
            self.set([])

    def get(self):
        with open(self._file) as f:
            try:
                out = json.load(f)
            except:
                self.set([])
                out = []

            self.length = len(out)
            return out

    def set(self, turns: list[dict]):
        with open(self._file, "w") as f:
            json.dump(turns, f)

    def append(self, turn: dict):
        turns = self.get()
        turns.append(turn)
        self.length += 1

        with open(self._file, "w") as f:
            json.dump(turns, f)

    def shift(self):
        turns = self.get()
        turns.pop(0)
        self.length -= 1

        with open(self._file, "w") as f:
            json.dump(turns, f)

class Memory:
    def __init__(self, context_total: int):
        self.context_used = 0
        self.context_total = context_total
        self.context_reserve = config.get("misc", "context_reserve", int)
        self.context_target = self.context_total - self.context_reserve

        self.turns = Turns()
        self.keep_recent_turns = config.get("misc", "keep_recent_turns", int)
        self.preserve_tools = config.get("misc", "preserve_tool_responses", bool)

        if self.keep_recent_turns < 0:
            raise ValueError("keep_recent_turns must be >= 0")
        
        self.persistent_prompts: list[dict] = []
        self._system_prompts: list[dict] = []
        self._current_turn: Optional[dict] = None

    def archive_turn(self, turn: dict):
        for message in turn["messages"]:
            role = message["role"]

            if role == "tool":
                continue

            if role == "assistant" and message.get("tool_calls"):
                continue

            db.add_message_entry(message["role"], message["content"])

    def get_messages(
        self, 
        system_prompts: bool = True,
        tool_calls: bool = True
    ):
        if system_prompts:
            out = list(self._system_prompts)
            out += self.persistent_prompts
        else:
            out = []

        for turn in self.turns.get():
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

    def add_persistent_prompt(
        self, 
        content: str,
        role: str = "assistant"
    ):
        self.persistent_prompts.append({
            "role": role,
            "content": content
        })

    def wipe_system_prompts(self):
        self._system_prompts = []

    def wipe_persistent_prompts(self):
        self.persistent_prompts = []

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

        if images: message["images"] = images
        if audio:  message["audio"] = audio

        self._current_turn["messages"].append(message)

        if finish_turn:
            self.finish_turn()
            self.prune_context()

    def prune_context(self):        
        removable = max(0, self.turns.length - self.keep_recent_turns)
        turns = self.turns.get()

        while self.context_used > self.context_target and (removable > 0):
            oldest = turns[0]

            # This is an approximation
            self.context_used = max(0, self.context_used - oldest["tokens"])

            self.turns.shift()
            turns.pop(0)
            removable -= 1

            log.info(f"History: pruned oldest turn ≈ {oldest["tokens"]} tokens")

    def finish_turn(self):
        if self._current_turn is None:
            return

        finished = self._current_turn

        if not self.preserve_tools:
            finished["messages"] = [
                m for m in finished["messages"]
                if m["role"] != "tool" and not m.get("tool_calls")
            ]
        
        finished["tokens"] = estimate_tokens(finished["messages"])

        self.turns.append(finished)
        self.archive_turn(finished)
        self._current_turn = None

    def unstage_turn(self):
        self._current_turn = None

    def wipe_context(self, soft: bool = False):
        log.info("Wiping current context")
        previous_turns = self.turns.get()

        self.turns.set([])

        if not soft:
            self._current_turn = None

        return previous_turns

    def restore_context(self, turns: list[dict]):
        self.turns.set(turns)

    # Used as a tool by model
    def clean_memory(self):
        """
        Forget current messages history / context
        """
        self.wipe_context(soft=True)