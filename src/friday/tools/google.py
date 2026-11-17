from src.friday.tools.shared import ToolResponse
from src.shared import FRIDAY_CACHE_DIR, FRIDAY_CONFIG_DIR

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as build_api

from typing import Optional
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import base64, os

__all__ = [
    "get_calendar_events",
    "get_google_tasks",
    "create_google_task",
    "complete_google_task",
    "delete_google_task",
    "get_google_emails"
]

API_SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CREDS_FILE = os.path.join(FRIDAY_CONFIG_DIR, "credentials.json")
TOKEN_FILE = os.path.join(FRIDAY_CACHE_DIR, "token.json")

if not os.path.exists(CREDS_FILE):
    raise FileNotFoundError(
        "In order to use google integrations, setup google OAauth project and save json credentials to credentials.json")

creds = None
gmail_api = None
calendar_api = None
tasks_api = None

def load_api():
    global creds, gmail_api, calendar_api, tasks_api

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, API_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_FILE, API_SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    gmail_api = build_api("gmail", "v1", credentials=creds)
    calendar_api = build_api("calendar", "v3", credentials=creds)
    tasks_api = build_api("tasks", "v1", credentials=creds)

def get_calendar_events(date: Optional[str] = None):
    """
    Takes date in format: "%Y-%m-%d". If omitted - today
    """

    if creds is None:
        load_api()

    calendar_info = calendar_api.calendars().get(calendarId="primary").execute()

    if date is None:
        date = datetime.today()
    else:
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except:
            return "Incorrect date format, %Y-%m-%d expected"

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

    return ToolResponse([
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
    if creds is None:
        load_api()

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
                "id": task.get("id"),
                "tasklist_id": task_list["id"],
            }
            for task in tasks
        ]

    return ToolResponse(out)

def create_google_task(
    title: str, 
    date: Optional[str] = None, 
    notes: Optional[str] = None, 
):
    """
    Takes date in format: "%Y-%m-%d". If omitted - today
    """
    if creds is None:
        load_api()

    if not date:
        due = datetime.today().strftime("%Y-%m-%dT00:00:00.000Z")
    else:
        try:
            due = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%dT00:00:00.000Z")
        except:
            return "Incorrect date format, %Y-%m-%d expected"

    body = { "title": title, "due": due }
    if notes:
        body["notes"] = notes

    task = tasks_api.tasks().insert(
        tasklist="@default",
        body=body,
    ).execute()

    return "Task was created"

def complete_google_task(tasklist_id: str, task_id: str):
    if creds is None:
        load_api()

    tasks_api.tasks().patch(
        tasklist=tasklist_id,
        task=task_id,
        body={"status": "completed"},
    ).execute()

    return "Task was marked as completed"

def delete_google_task(tasklist_id: str, task_id: str):
    if creds is None:
        load_api()

    tasks_api.tasks().delete(
        tasklist=tasklist_id,
        task=task_id,
    ).execute()

    return "Task was deleted"

def collect_gmail_bodies(part: dict, bodies: dict):
    mime_type = part.get("mimeType")
    data = part.get("body", {}).get("data")

    if mime_type in bodies and data:
        data += "=" * (-len(data) % 4)
        text = base64.urlsafe_b64decode(data).decode(
            "utf-8", errors="replace"
        )
        bodies[mime_type].append(text)

    for child in part.get("parts", []):
        collect_gmail_bodies(child, bodies)

def get_google_emails(
    date_from: str,
    date_until: Optional[str] = None,
    unread_only: bool = True
):  
    if creds is None:
        load_api()

    try:
        start_day = datetime.strptime(date_from, "%Y-%m-%d").date()
    except:
        return "Incorrect start_day format, %Y-%m-%d expected"

    if date_until:
        try:
            end_day = datetime.strptime(date_until, "%Y-%m-%d").date()
        except:
            return "Incorrect end_day format, %Y-%m-%d expected"
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
        collect_gmail_bodies(message["payload"], bodies)
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

    return ToolResponse(out)