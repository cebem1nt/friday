from configparser import ConfigParser
from src.shared import FRIDAY_CONFIG_PATHS
from typing import Any

import os

_config = None

def parse():
    global _config

    parser = ConfigParser(
        inline_comment_prefixes=("#")
    )

    for config_path in FRIDAY_CONFIG_PATHS:
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
        parse()
    
    value = _config[group][opt]
    if _type == bool:
        value = value.strip().lower()
        
        if value == "true":
            return True
        return False

    return _type(_config[group][opt])
