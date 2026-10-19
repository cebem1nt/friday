import ollama, subprocess, os, shutil

from typing import Optional, Any
from src.friday import common
from src import config

WEB_SEARCH_PROVIDER = config.get("misc", "web_search_provider")

APP_TYPES = {
    "browser":      ("x-scheme-handler/https", "x-scheme-handler/http"),
    "file_manager": ("inode/directory",),
    "pdf_viewer":   ("application/pdf",),
    "text_editor":  ("text/plain",),
    "image_viewer": ("image/png",),
    "video_player": ("video/mp4",),
    "audio_player": ("audio/mpeg",),
    "email_client": ("x-scheme-handler/mailto",),
}

def __run(args: list[str]):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False
    )

def __run_shell(cmd: str):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        shell=True
    )

def __popen(args: list[str]):
    subprocess.Popen(args)

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
    out = { "content": str(content) }
    
    if images: out["images"] = images
    if audio:  out["audio"] = audio

    return out

if WEB_SEARCH_PROVIDER == "ddgs":
    from ddgs import DDGS

    def web_search(query: str, max_results: int = 3):
        return __(DDGS().text(query, max_results=max_results))

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return __(DDGS().extract(url))

elif WEB_SEARCH_PROVIDER == "ollama":
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

def query_stored_messages(sql: str):
    """
    Args:
      sql to execute. Database has only "message" table
    """
    return __(common.db.query(sql))

def open_web_browser():
    __popen(["gtk-launch", __query_default("browser")])
    return __("Web browser launched successfully!")

def open_file_manager():
    __popen(["gtk-launch", __query_default("file_manager")])
    return __("File manager launched successfully!")

def get_content_from_user_clipboard():
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

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode == 0:
            return __(result.stdout)

    return __("Could not read clipboard. Install wl-clipboard (Wayland) or xclip/xsel (X11).")

def open_content(content: str):
    """
    Tries to open any given user's content in prefered app using xdg-open.

    Args:
      content: file path, web url, image path, etc.
    """

    out = __run(["xdg-open", content])

    if out.returncode != 0:
        return __(f"Could not launch: {out.stderr.strip()}")
    
    return __(f"{content} was launched sucessfully!")

def read_content_from_selected_file():
    """
    Gives you the content of user's selected file.
    User might refer it as current file or active file, or this file
    """

    path_like = get_content_from_clipboard()
    path_like = os.path.expanduser(path_like)

    if os.path.exists(path_like) and os.path.isfile(path_like):
        with open(path_like, "r") as f:
            return __(f.read())

    return __("Current user's selected content does not look like a file")

def look_at_the_screen():
    """
    Take a screenshot of what's going on user's screen right now.
    Use this in order to understand current screen state of the user
    """

    screenshot_cmd = config.get("misc", "screenshot_cmd")

    if screenshot_cmd is None:
        return __("Screenshot tool is not configured by user!")

    out = __run_shell(screenshot_cmd)
    
    if out.returncode != 0:
        return __("Screenshot failed!")

    return __("Screenshot of on-screen content", [out.stdout.strip()])

# def rick_roll(name: str):
#     """
#     Open website with given name
#     """

#     subprocess.run(["zen", "--new-window", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ&start_radio=1&pp=ygUXbmV2ZXIgZ29ubmEgZ2l2ZSB5b3UgdXCgBwE%3D"])
#     subprocess.run("sleep 5", shell=True)
#     subprocess.run("ydotool mousemove --absolute 450 250", shell=True)
#     subprocess.run("ydotool click 0xC0", shell=True)

#     return "Succes!"