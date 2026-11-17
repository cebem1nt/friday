from typing import Any, Optional
from src import config

MAX_TOOL_RESPONSE_LEN = config.get("misc", "max_tool_response_length")
TRIM_CONTENT = config.get("misc", "max_response_trim_content", bool)

if MAX_TOOL_RESPONSE_LEN.lower() == "unlimited":
    MAX_TOOL_RESPONSE_LEN = float('inf')
else:
    MAX_TOOL_RESPONSE_LEN = int(MAX_TOOL_RESPONSE_LEN)

class ToolResponse:
    __slots__ = ("content", "images", "audio")

    def __init__(
        self, 
        content: Any,
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None
    ):
        content = str(content)

        if len(content) > MAX_TOOL_RESPONSE_LEN:
            if TRIM_CONTENT:
                content = content[:MAX_TOOL_RESPONSE_LEN] + "..."
            else:
                content = f"Too big tool response ({len(content)}), try shorter request!"

        self.content = content
        self.images = images
        self.audio = audio

    def __str__(self):
        return self.content

def run(args: list[str]):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False
    )

def popen(args: list[str]):
    return subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def runsh(cmd: str):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        shell=True
    )

def popensh(cmd: str):
    return subprocess.Popen(
        cmd, 
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )