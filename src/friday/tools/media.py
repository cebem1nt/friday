from src.friday.tools.shared import ToolResponse, runsh
from src import config

__all__ = [
    "view_media"
]

def view_media(
    images: list[str] = None, 
    audio: list[str] = None
):
    return ToolResponse("Requested media", images, audio)

def look_at_the_screen():
    """
    Take a screenshot of user's screen
    """

    screenshot_cmd = config.get("misc", "screenshot_cmd")
    out = runsh(screenshot_cmd)
    
    if out.returncode != 0:
        return "Screenshot failed!"

    return ToolResponse("Screenshot of on-screen content", [out.stdout.strip()])
