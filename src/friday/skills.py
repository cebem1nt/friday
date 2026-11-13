from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from src.shared import FRIDAY_CONFIG_DIR
from src import log

import os, yaml

FRIDAY_SKILLS_DIR = os.path.join(FRIDAY_CONFIG_DIR, "skills")

@dataclass
class Skill:
    name: str
    description: str

    def __post_init__(self):
        if len(self.name) > 64:
            raise ValueError("skill name must be less than 64 chars")

        if len(self.description) > 1024:
            raise ValueError("skill description must be less than 1024 chars")

def parse_description(skill: str) -> Optional[Skill]:
    lines = []

    with open(skill) as f:
        lines = f.read().splitlines()
        
    if not lines:
        return log.warn(f"Empty skill: {skill}")

    if lines[0].strip() != "---":
        return log.error(f"Malformed skill: {skill}")

    try:
        end = lines.index("---", 1)
    except ValueError:
        return log.error(f"Malformed skill: {skill}")
    
    meta = yaml.safe_load("\n".join(lines[1:end]))
    name = meta.get("name")
    description = meta.get("description")

    if not isinstance(name, str) or not name.strip():
        return log.error(f"{skill}: missing required name")

    if not isinstance(description, str) or not description.strip():
        return log.error(f"{skill}: missing required description")

    if name != Path(skill).parent.name:
        return log.error(f"{skill}: name should match skill's directory")

    try:
        return Skill(name, description)
    except ValueError as e:
        return log.error(f"{skill}: {e}")

def discover() -> list[Skill]:
    skills = []

    if not os.path.exists(FRIDAY_SKILLS_DIR):
        return []

    for entry in os.scandir(FRIDAY_SKILLS_DIR):
        if not entry.is_dir():
            continue

        md = os.path.join(entry, "SKILL.md")

        if not os.path.exists(md):
            continue

        if description := parse_description(md):
            skills.append(description)

    return skills
        
def get_skill(name: str) -> str:
    skill_dir = os.path.join(FRIDAY_SKILLS_DIR, name)

    if not os.path.exists(skill_dir):
        return "Unknown skill!"

    md = os.path.join(skill_dir, "SKILL.md")

    if not os.path.exists(md):
        return "SKILL.md does not exist!"

    with open(md) as f:
        lines = f.read().splitlines()
        end = lines.index("---", 1)
        return "\n".join(lines[end + 1:]).lstrip()
