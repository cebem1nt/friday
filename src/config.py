import os
from configparser import ConfigParser
from typing import Any

CONFIG_HOME = os.path.expanduser("~/.config/")
CONFIG_PATHS = [
    os.path.join(os.getenv("XDG_CONFIG_HOME", CONFIG_HOME), "friday", "config.ini"),
    "/etc/friday/config.ini"
]

_config = None

def _populate_config():
    global _config

    parser = ConfigParser(
        inline_comment_prefixes=("#")
    )

    for config_path in CONFIG_PATHS:
        if os.path.exists(config_path):
            parser.read(config_path)
        
            _config = {
                section: dict(parser[section]) for section in parser.sections()
            }

            break
    else:
        raise Exception("No config file!")

def get(group: str, opt: str, _type=str):
    if _config is None:
        _populate_config()
    
    try:
        return _type(_config[group][opt])
    except:
        return None

# Hell yeah, im going to make friday be able to modify itself at runtime
def set(group: str, opt: str, value: Any):
    if _config is None:
        _populate_config()

    _config[group][opt] = str(value)