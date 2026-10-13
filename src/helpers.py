import random
from datetime import datetime

def today():
    return datetime.today().strftime('%Y-%m-%d')

def random_thinking_quote():
    return random.choice([
        "Let me think",
        "Let me think about it",
        "I should think about it",
        "I'm thinking",
        "Okay, let me think for a moment",
        "Thinking",
        "I have to think about it",
        "Wait please, I gotta think"
    ])