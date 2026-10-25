from typing import Optional, Any
from src import config, shared

import subprocess, os, shutil, fnmatch

WEB_SEARCH_PROVIDER = config.get("misc", "web_search_provider")
MAX_LEN = config.get("misc", "max_tool_response_length")

if MAX_LEN.lower() == "unlimited":
    MAX_LEN = float('inf')
else:
    MAX_LEN = int(MAX_LEN)

TRIM_CONTENT = config.get("misc", "max_response_trim_content", bool)

APP_TYPES = {
    "browser":      ("x-scheme-handler/https", "x-scheme-handler/http"),
    "file_manager": ("inode/directory"),
    "pdf_viewer":   ("application/pdf"),
    "text_editor":  ("text/plain"),
    "image_viewer": ("image/png"),
    "video_player": ("video/mp4"),
    "audio_player": ("audio/mpeg"),
    "email_client": ("x-scheme-handler/mailto")
}

def __run(args: list[str]):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False
    )

def __popen(args: list[str]):
    return subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def __run_shell(cmd: str):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        shell=True
    )

def __popen_shell(cmd: str):
    return subprocess.Popen(
        cmd, 
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )

def __query_default(app: str) -> Optional[str]:
    mime_types = APP_TYPES[app]

    for mime_type in mime_types:
        out =__run(["xdg-mime", "query", "default", mime_type])
        app_id = out.stdout.strip()

        if out.returncode == 0 and app_id:
            return app_id
    
    return None

# Use to wrap tool responses
def __(
    content: Any, 
    images: Optional[list[str]] = None, 
    audio: Optional[list[str]] = None
) -> dict:
    content = str(content)

    if (length := len(content)) > MAX_LEN:
        if TRIM_CONTENT:
            content = content[:MAX_LEN] + "..."
        else:
            content = f"Too big response ({length}), try shorter request!"

    out = { "content": content }
    
    if images: 
        out["images"] = images
    
    if audio:
        out["audio"] = audio

    return out

if WEB_SEARCH_PROVIDER == "ddgs":
    from ddgs import DDGS

    def web_search(query: str, max_results: int = 5):
        return __(DDGS().text(query, max_results=max_results))

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return __(DDGS().extract(url))

elif WEB_SEARCH_PROVIDER == "ollama":
    import ollama

    if not os.getenv("OLLAMA_API_KEY"):
        raise AssertionError("OLLAMA_API_KEY should be set in order to use ollama web search")

    def web_search(query: str, max_results: int = 2):
        return __(ollama.web_search(query, max_results))

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return __(ollama.web_fetch(url))

elif WEB_SEARCH_PROVIDER == "searxng":
    import requests, trafilatura

    def web_search(query: str, max_results: int = 2) -> dict:
        max_results = max(1, min(max_results, 8))

        response = requests.get(
            config.get("misc", "searxng_url"),
            params={"q": query, "format": "json"},
            timeout=15,
        )

        response.raise_for_status()

        results = response.json().get("results", [])[:max_results]
        found = [
            {
                "title": item.get("title", ""),
                "body": item.get("content", "")[:700],
                "url": item.get("url", ""),
            }
            for item in results
        ]

        return __(found)

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        text = trafilatura.extract(
            response.text,
            url=url,
            include_comments=False,
            include_tables=True,
        )

        return __(text or "")

def run_messages_history_sql(sql: str):
    return __(shared.db.run_sql(sql))

def run_shell(cmd: str):
    out = __run_shell(cmd)

    return __({
        "returncode": out.returncode, 
        "stdout": out.stdout, 
        "stderr": out.stderr
    })

def spawn_process(cmd: list[str]):
    try:
        __popen(cmd)
        return "Process spawned"
    except:
        return "Could not spawn process!"

def xdg_open(uri: str):
    """
    Open a file path or URL with its default desktop app.
    """
    __popen_shell(f"xdg-open {uri}")
    return __(f"{uri} was opened sucessfully!")

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

        result = __run(command)

        if result.returncode == 0:
            return __(result.stdout)

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

def look_at_the_screen():
    """
    Take a screenshot of what's going on user's screen right now.
    Use this in order to understand current screen state of the user
    """

    screenshot_cmd = config.get("misc", "screenshot_cmd")

    if screenshot_cmd is None:
        return "Screenshot tool is not configured by user!"

    out = __run_shell(screenshot_cmd)
    
    if out.returncode != 0:
        return "Screenshot failed!"

    return __("Screenshot of on-screen content", [out.stdout.strip()])

def read_file(path: str):
    try:
        with open(path, "r") as f:
            return __(f.read())

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
    directory = os.path.expanduser(
        os.path.expandvars(directory))

    if not os.path.exists(directory):
        return "Directory does not exist"

    os.chdir(directory)
    return "Sucess"

def view_media(images: list[str] = None, audio: list[str] = None):
    return __("Requested media", images, audio)

def search_files(
    patterns: list[str] = [], 
    begin: str = "~"
):
    """
    Args:
        pattern: file pattern to search, supports wildcards
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
                    return __(matches)
                matches.append(os.path.join(folder, name))

    return __(matches)