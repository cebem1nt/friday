from src.shared import db
from src import config
from src.friday.tools.shared import (
    ToolResponse,
    popen, popensh,
    run, runsh,
)

from datetime import datetime
from time import sleep
from urllib.parse import urlsplit

import subprocess, os, shutil, fnmatch

__all__ = [
    "run_messages_history_sql",
    "run_shell",
    "type_content",
    "spawn_process",
    "xdg_open",
    "get_user_selection",
    "paste_to_user_selection",
    "read_file",
    "write_to_file",
    "change_directory",
    "search_files",
    "time_now"
]

def run_messages_history_sql(sql: str):
    return ToolResponse(db.run_sql(sql))

def run_shell(cmd: str):
    out = runsh(cmd)

    return ToolResponse({
        "returncode": out.returncode, 
        "stdout": out.stdout, 
        "stderr": out.stderr
    })

def type_content(content: str):
    """
    Pastes given content into user's active input field
    """

    paste_to_user_selection(content)

    if os.environ.get("WAYLAND_DISPLAY"):
        command = ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"]
    else:
        command = ["xdotool", "key", "--clearmodifiers", "ctrl+v"]

    try:
        proc = run(command)
        if proc.returncode != 0:
            return f"{command[0]} failed!"
    except FileNotFoundError:
        return f"Could not paste content {command[0]} is not installed!"

    return "Content was pasted successfully"

def spawn_process(cmd: str):
    try:
        proc = popensh(cmd)
        sleep(1)

        if proc.poll() is not None and proc.returncode != 0:
            return f"Could not run: {proc.stderr.read()}"

        return "Process spawned"
    except Exception as e:
        return f"Could not spawn: ({e})"

def xdg_open(uri: str):
    """
    Open a file path or URL with its default desktop app.
    """
    
    if not urlsplit(uri).scheme:
        uri = os.path.expanduser(os.path.expandvars(uri))

    proc = popen(["xdg-open", uri])
    sleep(0.5)

    if proc.poll() is not None and proc.returncode != 0:
        return f"Could not run: {proc.stderr.read().strip()}"
    
    return f"{uri} was opened sucessfully!"

def get_user_selection():
    if os.environ.get("WAYLAND_DISPLAY"):
        commands = [
            ["wl-paste", "--no-newline"]
        ]
    else:
        commands = [
            ["xclip", "-selection", "clipboard", "-out"],
            ["xsel", "--clipboard", "--output"]
        ]

    for command in commands:
        if not shutil.which(command[0]):
            continue

        result = run(command)

        if result.returncode == 0:
            return ToolResponse(result.stdout)

    return "Could not read clipboard. Install wl-clipboard (Wayland) or xclip/xsel (X11)."

def paste_to_user_selection(content: str):
    if os.environ.get("WAYLAND_DISPLAY"): 
        commands = [ 
            ["wl-copy"] 
        ] 
    else: 
        commands = [
            ["xclip", "-selection", "clipboard"], 
            ["xsel", "--clipboard"] 
        ]

    for command in commands:
        if not shutil.which(command[0]):
            continue

        try:
            result = subprocess.run(
                command,
                input=content,
                text=True,
                capture_output=True,
            )
        except OSError:
            continue

        if result.returncode == 0:
            return "Successfully pasted to clipboard."

    return "Could not paste to clipboard. Install wl-clipboard (Wayland) or xclip/xsel (X11)."

def read_file(path: str):
    path = os.path.expanduser(
        os.path.expandvars(path))

    try:
        with open(path, "r") as f:
            return ToolResponse(f.read())

    except Exception as e:
        return f"Could not read file: {e}"

def write_to_file(
    path: str, 
    content: str, 
    append_to_the_end: bool = False
):
    path = os.path.expanduser(
        os.path.expandvars(path))

    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

    mode = "a" if append_to_the_end else "w"

    with open(path, mode, encoding="utf-8") as f:
        f.write(content)

    return f"Content was written to {path}"

def change_directory(directory: str):
    directory = os.path.expanduser(os.path.expandvars(directory))

    if not os.path.exists(directory):
        return "Directory does not exist"

    os.chdir(directory)
    return "Sucess"

def search_files(
    patterns: list[str] = [], 
    begin: str = "~"
):
    """
    Args:
        pattern: list of file patterns to search, supports wildcards
        begin: Search root - a path, or environment variable.
    """

    begin = os.path.expanduser(
        os.path.expandvars(begin))

    if not os.path.exists(begin):
        return "Begin directory does not exist"

    matches = []
    skipped_dirs = {".cache", ".git", "node_modules", "__pycache__"}

    for folder, dirs, files in os.walk(begin):
        dirs[:] = [d for d in dirs if d not in skipped_dirs]

        for name in files:
            if any(fnmatch.fnmatchcase(name.casefold(), p.casefold())
                   for p in patterns):
                if len(matches) == 100:
                    matches.append("...Result limit reached.")
                    return ToolResponse(matches)
                matches.append(os.path.join(folder, name))

    return ToolResponse(matches)

def time_now():
    return ToolResponse(datetime.now())
