from typing import Optional, Any
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from src import config, shared

import subprocess, os, shutil, fnmatch, sys, base64

WEB_SEARCH_PROVIDER = config.get("misc", "web_search_provider")
MAX_TOOL_RESPONSE_LEN = config.get("misc", "max_tool_response_length")
USE_GOOGLE_TOOLS = config.get("misc", "use_google_tools", bool)

if MAX_TOOL_RESPONSE_LEN.lower() == "unlimited":
    MAX_TOOL_RESPONSE_LEN = float('inf')
else:
    MAX_TOOL_RESPONSE_LEN = int(MAX_TOOL_RESPONSE_LEN)

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

    if (length := len(content)) > MAX_TOOL_RESPONSE_LEN:
        if TRIM_CONTENT:
            content = content[:MAX_TOOL_RESPONSE_LEN] + "..."
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

    def web_search(query: str, max_results: int = 10):
        """
        max_results should be >= 3
        """
        return __(DDGS().text(query, max_results=max_results))

    def web_search_news(query: str, max_results: int = 10):
        return __(DDGS().news(query, max_results=max_results))

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return __(DDGS().extract(url, fmt="text_rich"))

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

if USE_GOOGLE_TOOLS:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as __build_api

    API_SCOPES = [
        "https://www.googleapis.com/auth/tasks",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    if not os.path.exists("credentials.json"):
        raise FileNotFoundError(
            "In order to use google integrations, setup google OAauth project and save json credentials to credentials.json")

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", API_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", API_SCOPES
            )

            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as f:
            f.write(creds.to_json())

    gmail_api = __build_api("gmail", "v1", credentials=creds)
    calendar_api = __build_api("calendar", "v3", credentials=creds)
    tasks_api = __build_api("tasks", "v1", credentials=creds)

    def get_calendar_events(date: Optional[str] = None):
        """
        Takes date in format: "%Y-%m-%d". If omitted - today
        """

        calendar_info = calendar_api.calendars().get(calendarId="primary").execute()

        if date is None:
            date = datetime.today()
        else:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        
        tz = ZoneInfo(calendar_info["timeZone"])
        start = datetime.combine(date, time.min, tzinfo=tz)
        end = start + timedelta(days=1)

        events = calendar_api.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])

        return __([
            {
                "title": event.get("summary", "(no title)"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                **({"location": event["location"]} if event.get("location") else {}),
                **({"description": event["description"]} if event.get("description") else {}),
            }
            for event in events
        ])

    def get_google_tasks():
        task_lists = tasks_api.tasklists().list().execute().get("items", [])
        out = {}

        for task_list in task_lists:
            tasks = tasks_api.tasks().list(
                tasklist=task_list["id"],
                maxResults=100,
                showCompleted=False,
            ).execute().get("items", [])

            out[task_list["title"]] = [
                {
                    "title": task.get("title"),
                    "due": task.get("due"),
                    "notes": task.get("notes"),
                    "id": task.get("id")
                }
                for task in tasks
            ]

        return __(out)

    def create_google_task(
        title: str, 
        date: Optional[str] = None, 
        notes: Optional[str] = None, 
    ):
        """
        Takes date in format: "%Y-%m-%d". If omitted - today
        """
        if not date:
            due = datetime.today().strftime("%Y-%m-%dT00:00:00.000Z")
        else:
            due = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%dT00:00:00.000Z")

        body = { "title": title, "due": due }
        if notes:
            body["notes"] = notes

        task = tasks_api.tasks().insert(
            tasklist="@default",
            body=body,
        ).execute()

        return "Task was created"

    def complete_google_task(task_id: str):
        tasks_api.tasks().patch(
            tasklist="@default",
            task=task_id,
            body={"status": "completed"},
        ).execute()

        return "Task was marked as completed"

    def delete_google_task(task_id: str):
        tasks_api.tasks().delete(
            tasklist="@default",
            task=task_id,
        ).execute()

        return "Task was deleted"

    def __collect_gmail_bodies(part, bodies):
        mime_type = part.get("mimeType")
        data = part.get("body", {}).get("data")

        if mime_type in bodies and data:
            data += "=" * (-len(data) % 4)
            text = base64.urlsafe_b64decode(data).decode(
                "utf-8", errors="replace"
            )
            bodies[mime_type].append(text)

        for child in part.get("parts", []):
            __collect_gmail_bodies(child, bodies)

    def get_google_emails(
        date_from: str,
        date_until: Optional[str] = None,
        unread_only: bool = True
    ):      
        start_day = datetime.strptime(date_from, "%Y-%m-%d").date()

        if date_until:
            end_day = datetime.strptime(date_until, "%Y-%m-%d").date()
        else:
            end_day = datetime.today().date()

        # Gmail's before: boundary is exclusive, so add one day to include date_until.
        next_day = end_day + timedelta(days=1)

        query = f"-in:trash -in:spam -category:promotions -category:social after:{start_day:%Y/%m/%d} before:{next_day:%Y/%m/%d}"

        if unread_only:
            query += " is:unread"

        messages = gmail_api.users().messages().list(
            userId="me",
            q=query,
            maxResults=100,
        ).execute().get("messages", [])

        out = []

        for item in messages:
            message = gmail_api.users().messages().get(
                userId="me",
                id=item["id"],
                format="full",
            ).execute()

            headers = {
                h["name"].lower(): h["value"]
                for h in message["payload"].get("headers", [])
            }

            bodies = {"text/plain": [], "text/html": []}
            __collect_gmail_bodies(message["payload"], bodies)
            body = (
                "\n".join(bodies["text/plain"])
                or "\n".join(bodies["text/html"])
                or message.get("snippet", "")
            )

            out.append({
                "from": headers.get("from"),
                "subject": headers.get("subject"),
                "date": headers.get("date"),
                "body": body,
            })

        return __(out)

def run_messages_history_sql(sql: str):
    return __(shared.db.run_sql(sql))

def run_shell(cmd: str):
    out = __run_shell(cmd)

    return __({
        "returncode": out.returncode, 
        "stdout": out.stdout, 
        "stderr": out.stderr
    })

def spawn_process(args: list[str]):
    try:
        __popen(args)
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
    """

    screenshot_cmd = config.get("misc", "screenshot_cmd")
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
                    return __(matches)
                matches.append(os.path.join(folder, name))

    return __(matches)

def time_now():
    return __(datetime.now())

# TODO these reminders and timers are very fragile and
# might be confusing for the model. Needs rework

# TODO possibly more sophisticated reminders system

def set_timer(
    hours: int,
    minutes: int, 
    seconds: int,
    content: str
):
    total = seconds + (minutes * 60) + (hours * 60 * 60) 
    message = f"This is a message from timer - {content}"

    try:
        subprocess.Popen(f"sleep {total} && {sys.argv[0]} -a '{message}'", shell=True)
    except:
        return "Could not set timer!"

    return "Timer was set!"

def remind_at(
    hours: int,
    minutes: int, 
    seconds: int,
    content: str
):
    now = datetime.now()
    target = now.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)

    if target <= now:
        target += timedelta(days=1) # Won't survive if host turns off

    message = f"This is a message from reminder - {content}"

    if shutil.which("at"):
        try:
            subprocess.run(
                ["at", "-t", target.strftime("%Y%m%d%H%M.%S")],
                input=f"{sys.argv[0]} -a '{message}'\n", 
                text=True, 
                check=True
            )
            return "Reminder was set!"
        except (OSError, subprocess.CalledProcessError):
            pass

    try:
        total = (target - now).total_seconds()
        subprocess.Popen(f"sleep {total} && {sys.argv[0]} -a '{message}'", shell=True)
    except:
        return "Could not set reminder!"

    return "Reminder was set!"

def type_content(content: str):
    """
    Types/writes given content to user's active input field
    """

    if os.environ.get("WAYLAND_DISPLAY"):
        command = ["wtype", content]
    else:
        command = ["xdotool", "type", "--clearmodifiers", content]

    try:
        proc = __run(command)
        if proc.returncode != 0:
            return f"{command[0]} failed!"
    except FileNotFoundError:
        return f"Could not type content {command[0]} is not installed!"

    return "Content was typed successfully"
