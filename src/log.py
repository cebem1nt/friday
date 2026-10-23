_log_level = 4

def set_log_level(lvl: int):
    global _log_level
    _log_level = lvl

def debug(msg: str):
    if _log_level > 3:
        print(f"[\x1B[0;35mDEBUG\x1B[0m] {msg}", flush=True)

def info(msg: str):
    if _log_level > 2:
        print(f"[\x1B[0;34mINFO\x1B[0m] {msg}")

def warn(msg: str):
    if _log_level > 1:
        print(f"[\x1B[0;33mWARNING\x1B[0m] {msg}", flush=True)

def error(msg: str):
    if _log_level > 0:
        print(f"[\x1B[0;31mERROR\x1B[0m] {msg}", flush=True)