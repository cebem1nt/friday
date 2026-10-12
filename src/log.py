LOG_LEVEL = 3

def set_log_level(lvl: int):
    global LOG_LEVEL
    LOG_LEVEL = lvl

def info(msg: str):
    if LOG_LEVEL >= 3:
        print(f"[\x1B[0;34mINFO\x1B[0m] {msg}")

def ok(msg: str):
    if LOG_LEVEL >= 2:
        print(f"[\x1B[0;32mOK\x1B[0m] {msg}")

def warn():
    if LOG_LEVEL >= 1:
        print(f"[\x1B[0;33mWARNING\x1B[0m] {msg}", flush=True)

def error():
    if LOG_LEVEL >= 0:
        print(f"[\x1B[0;31mERROR\x1B[0m] {msg}", flush=True)