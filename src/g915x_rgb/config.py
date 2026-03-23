"""Application configuration — tracks last-used profile and settings."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "g915x-rgb"
CONFIG_PATH = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_last_profile() -> str | None:
    return load_config().get("last_profile")


def set_last_profile(profile_name: str) -> None:
    config = load_config()
    config["last_profile"] = profile_name
    save_config(config)
