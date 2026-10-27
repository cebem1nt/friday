import os

from typing import Optional

_log_level = 4
_log_file = None

def __log_to_file(content: str):
    if _log_file is None:
        return

    with open(_log_file, "a") as f:
        f.write(content)
        f.write('\n')
        f.flush()

def set_log_level(lvl: int):
    global _log_level
    _log_level = lvl

def set_log_file(file_path: Optional[str]):
    global _log_file

    if file_path is None:
        _log_file = None
        return

    file_path = os.path.expanduser(file_path)
    _log_file = file_path

def debug(msg: str):
    if _log_level > 3:
        print(f"[\x1B[0;35mDEBUG\x1B[0m] {msg}", flush=True)
        __log_to_file(f"[DEBUG] {msg}")

def info(msg: str):
    if _log_level > 2:
        print(f"[\x1B[0;34mINFO\x1B[0m] {msg}")
        __log_to_file(f"[INFO] {msg}")

def warn(msg: str):
    if _log_level > 1:
        print(f"[\x1B[0;33mWARNING\x1B[0m] {msg}", flush=True)
        __log_to_file(f"[WARNING] {msg}")

def error(msg: str):
    if _log_level > 0:
        print(f"[\x1B[0;31mERROR\x1B[0m] {msg}", flush=True)
        __log_to_file(f"[ERROR] {msg}")

def raw(msg: str):
    print(msg, flush=True)
    __log_to_file(msg)