import ollama, subprocess, os, shutil

from typing import Optional
from src import config

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

def __query_default(mime_types: tuple[str, ...]) -> Optional[str]:
    for mime_type in mime_types:
        out =__run(["xdg-mime", "query", "default", mime_type])
        app_id = out.stdout.strip()

        if out.returncode == 0 and app_id:
            return app_id
    
    return None

def __clip_contents(result, limit = 8000):
    text = str(result)
    if len(text) > limit:
        return text[:limit] + "\n... [truncated]"

    return text

# Use to wrap tool responses
def __(
    text: str, 
    images: Optional[list[str]] = None, 
    audio: Optional[list[str]] = None
) -> dict:
    out = { "content": text }
    
    if images: out["images"] = images
    if audio:  out["audio"] = audio

    return out

def web_search(query: str, max_results = 3):
    """
    Performs a web search

    Args:
      query: The query to search for
      max_results: The maximum number of results to return (default: 3)

    Returns:
      WebSearchResponse with the search results
    """
    result = ollama.web_search(query, max_results)
    return __(__clip_contents(result))

def web_fetch(url: str):
    """
    Fetches the content of a web page for the provided URL.

    Args:
      url: The URL to fetch

    Returns:
      WebFetchResponse with the fetched result
    """
    return __clip_contents(ollama.web_fetch(url))



def open_browser():
    """
    Tries to just open user's web browser.
    """

    __popen(["gtk-launch", __query_default(APP_TYPES["browser"])])
    return __("Browser launched successfully!")

def open_file_manager():
    """
    Tries to just open user's file manager
    """

    __popen(["gtk-launch", __query_default(APP_TYPES["file_manager"])])
    return __("File manager launched successfully!")

def get_content_from_clipboard():
    """
    Get content from user's clipboard. 

    If could not read from clipboard, returns error message about it
    """

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


def open_content_from_clipboard():
    """
    Use if user asked to open currently selected content, "this" file, "this" link, or just "this" or maybe "open it".
    """

    return open_content(get_content_from_clipboard()["content"])

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