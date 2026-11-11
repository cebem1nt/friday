from datetime import datetime
from contextlib import contextmanager, closing
from src import config

import random, os, sqlite3, subprocess, sys

CACHE_HOME = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache/"))
CONFIG_HOME = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config/"))

FRIDAY_SOCKET_PATH = os.path.join(os.environ["XDG_RUNTIME_DIR"], "friday.sock")
FRIDAY_LOCK_PATH = os.path.join(os.environ["XDG_RUNTIME_DIR"], "friday.lock")
FRIDAY_CACHE_DIR = os.path.join(CACHE_HOME, "friday")
FRIDAY_CONFIG_DIR = os.path.join(CONFIG_HOME, "friday")

FRIDAY_CONFIG_PATHS = [
    os.path.join(CONFIG_HOME, "friday", "config.ini"),
    "/etc/friday/config.ini"
]

# From papirus icon theme
# TODO pack these icons with friday (if it's okay)
FRIDAY_ICONS = [f"si-syncthing-{n}" for n in range(1, 12)]

THINKING_QUOTES = [
    quote.strip()
    for quote in config.get("misc", "thinking_quotes").split(";")
        if quote.strip()
]

class Database:
    def __init__(self):
        data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share/"))
        
        self.db_dir = os.path.join(data_home, "friday")
        self.db_file = os.path.join(self.db_dir, "history.db")

        with self.con() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS message (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)

            con.execute("""
                CREATE TABLE IF NOT EXISTS setting (
                    id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL
                )
            """)

    @contextmanager
    def con(self):
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

        with closing(sqlite3.connect(self.db_file)) as con:
            with con:
                yield con

    def add_message_entry(self, role: str, content: str):
        with self.con() as con:
            con.execute("INSERT INTO message (role, content) VALUES (?, ?)", (role, content))

    def run_sql(self, sql: str, limit: int = 25):
        if limit < 1:
            raise ValueError("limit must be at least 1")

        results = []
        statement = ""

        # SQLite string literals escape apostrophes by doubling them, not with \'.
        # Model can still fuck this up despite system prompt.
        sql = sql.replace("\\'", "''")

        with self.con() as con:
            statements = []

            for char in sql:
                statement += char
                if char == ";" and sqlite3.complete_statement(statement):
                    statements.append(statement)
                    statement = ""

            if statement.strip():
                statements.append(statement)

            for statement in statements:
                cursor = con.execute(statement)

                if cursor.description is not None:
                    remaining = limit - len(results)
                    if remaining <= 0:
                        break

                    columns = [column[0] for column in cursor.description]
                    results.extend(
                        dict(zip(columns, row))
                        for row in cursor.fetchmany(remaining)
                    )

        return results

db = Database()

def random_thinking_quote():
    return random.choice(THINKING_QUOTES)

def today():
    weekday_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today = datetime.today()
    return today.strftime(f'%Y-%m-%d {weekday_map[today.weekday()]}') 

def notify(
    message: str, 
    details: str,
    is_syncronous: bool = False
):
    if not config.get("misc", "send_notifications", bool):
        return

    icon = random.choice(FRIDAY_ICONS)
    args = [
        "notify-send", message, details,
            "-a", "friday", 
            "-i", icon 
    ]

    if is_syncronous:
        args.append("-h")
        args.append(f"string:x-canonical-private-synchronous:{sys.argv[0]}")

    subprocess.Popen(args)

def parse_duration(value: str) -> float:
    value = value.strip().lower()

    if len(value) < 2:
        raise ValueError("Use a number followed by s, m, or h")

    unit = value[-1]
    multipliers = { "s": 1, "m": 60, "h": 3600 }

    if unit not in multipliers:
        raise ValueError("Duration unit must be s, m, or h")

    try:
        amount = float(value[:-1].strip())
    except ValueError:
        raise ValueError("Invalid duration amount") from None

    if amount < 0:
        raise ValueError("Duration cannot be negative")

    return amount * multipliers[unit]

def friday_server_is_running():
    if not os.path.exists(FRIDAY_LOCK_PATH):
        return False

    with open(FRIDAY_LOCK_PATH) as f:
        content = f.read()

        try:
            pid = int(content)
            os.kill(pid, 0)
            return True

        except:
            return False
