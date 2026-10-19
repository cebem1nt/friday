from datetime import datetime
from contextlib import contextmanager, closing

import random, os, sqlite3

THINKING_QUOTES = [
    "Processing your request",
    "I gotta think on a response",
    "Let my brain work a little",
    "Let me think",
    "Let me think about it",
    "I should think about it",
    "I'm thinking",
    "Okay, let me think for a moment",
    "Thinking",
    "I have to think about it",
    "Wait please, I gotta think",
    "Give me a second to think",
    "Let me put my thoughts together",
    "Working through it",
    "One moment while I think",
    "Thinking it through",
    "Let me mull that over",
    "Gathering my thoughts",
    "Hmm, let me think",
    "Just a moment—I'm figuring it out",
    "Let me work this out",
    "Taking a moment to think",
    "My gears are turning",
    "Let's see... thinking",
    "I'm piecing together an answer",
    "Hold on, let me reason this out",
    "Running that through my head",
    "Give me a beat to think",
    "I'm sorting through the details",
    "Let me come up with a good answer",
    "Hold on a second",
]

def random_thinking_quote():
    return random.choice(THINKING_QUOTES)

def today():
    return datetime.today().strftime('%Y-%m-%d')

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

    def query(self, sql: str, limit: int = 25):
        if limit < 1:
            raise ValueError("limit must be at least 1")

        with self.con() as con:
            con.execute("PRAGMA query_only = ON")
            cursor = con.execute(sql)

            if cursor.description is None:
                return []

            columns = [column[0] for column in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchmany(limit)
            ]

db = Database()