LOG_LEVEL = 4

def set_log_level(lvl: int):
    global LOG_LEVEL
    LOG_LEVEL = lvl

def debug(msg: str):
    if LOG_LEVEL > 3:
        print(f"[\x1B[0;35mDEBUG\x1B[0m] {msg}")

def info(msg: str):
    if LOG_LEVEL > 2:
        print(f"[\x1B[0;34mINFO\x1B[0m] {msg}")

def warn(msg: str):
    if LOG_LEVEL > 1:
        print(f"[\x1B[0;33mWARNING\x1B[0m] {msg}", flush=True)

def error(msg: str):
    if LOG_LEVEL > 0:
        print(f"[\x1B[0;31mERROR\x1B[0m] {msg}", flush=True)