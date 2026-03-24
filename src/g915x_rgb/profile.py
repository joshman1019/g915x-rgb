"""Profile management for G915 X RGB settings.

Profiles are stored as JSON in ~/.config/g915x-rgb/profiles/.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .keyboard_layout import KEY_BY_NAME, KEY_GROUPS, G915X_KEYS

PROFILES_DIR = Path.home() / ".config" / "g915x-rgb" / "profiles"
RULES_PATH = Path.home() / ".config" / "g915x-rgb" / "rules.json"


@dataclass
class Profile:
    name: str
    group_colors: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    key_colors: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    startup_animation: bool = False

    def get_effective_color(self, address: int) -> tuple[int, int, int]:
        """Get the color for a key, checking individual first, then group."""
        if address in self.key_colors:
            return self.key_colors[address]

        # Find which group this key belongs to
        for key in G915X_KEYS:
            if key.address == address and key.group in self.group_colors:
                return self.group_colors[key.group]

        return (0, 0, 0)

    def get_all_key_colors(self) -> dict[int, tuple[int, int, int]]:
        """Resolve all key colors (group defaults + individual overrides)."""
        colors = {}
        for key in G915X_KEYS:
            if key.group in self.group_colors:
                colors[key.address] = self.group_colors[key.group]
        colors.update(self.key_colors)
        return colors

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": 1,
            "startup_animation": self.startup_animation,
            "groups": {
                g: f"{r:02x}{g_:02x}{b:02x}"
                for g, (r, g_, b) in self.group_colors.items()
            },
            "individual_keys": {
                str(addr): f"{r:02x}{g:02x}{b:02x}"
                for addr, (r, g, b) in self.key_colors.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        p = cls(name=data.get("name", "Unnamed"))
        p.startup_animation = data.get("startup_animation", False)

        for group, color_hex in data.get("groups", {}).items():
            p.group_colors[group] = _parse_hex(color_hex)

        for addr_str, color_hex in data.get("individual_keys", {}).items():
            p.key_colors[int(addr_str)] = _parse_hex(color_hex)

        return p

    def save(self) -> Path:
        """Save profile to disk."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(self.name) + ".json"
        path = PROFILES_DIR / filename
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, path: Path) -> "Profile":
        with open(path) as f:
            return cls.from_dict(json.load(f))


def list_profiles() -> list[Path]:
    """List all saved profile files."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(PROFILES_DIR.glob("*.json"))


def load_all_profiles() -> list[Profile]:
    """Load all saved profiles."""
    profiles = []
    for path in list_profiles():
        try:
            profiles.append(Profile.load(path))
        except (json.JSONDecodeError, KeyError):
            continue
    return profiles


def import_from_g810_script(script_path: str) -> Profile:
    """Import a profile from a g810-led/g915x-led shell script."""
    p = Profile(name=Path(script_path).stem)

    with open(script_path) as f:
        for line in f:
            line = line.strip()
            # Match: g915x-led -g gkeys 4a0004
            m = re.match(r"g\d+x?-led\s+-g\s+(\w+)\s+([0-9a-fA-F]{6})", line)
            if m:
                group = m.group(1)
                color = _parse_hex(m.group(2))
                p.group_colors[group] = color
                continue

            # Match: g915x-led -k space 486902
            m = re.match(r"g\d+x?-led\s+-k\s+(\w+)\s+([0-9a-fA-F]{6})", line)
            if m:
                key_name = m.group(1)
                color = _parse_hex(m.group(2))
                if key_name in KEY_BY_NAME:
                    p.key_colors[KEY_BY_NAME[key_name].address] = color

    return p


def create_default_profile() -> Profile:
    """Create a default white profile."""
    p = Profile(name="Default")
    p.group_colors["keys"] = (255, 255, 255)
    p.group_colors["fkeys"] = (200, 200, 255)
    p.group_colors["modifiers"] = (180, 180, 180)
    p.group_colors["arrows"] = (200, 200, 255)
    p.group_colors["numeric"] = (200, 200, 200)
    p.group_colors["functions"] = (180, 180, 255)
    p.group_colors["gkeys"] = (100, 0, 200)
    p.group_colors["logo"] = (100, 0, 200)
    p.group_colors["indicators"] = (200, 200, 200)
    p.group_colors["multimedia"] = (150, 150, 200)
    return p


def _parse_hex(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    return (
        int(hex_str[0:2], 16),
        int(hex_str[2:4], 16),
        int(hex_str[4:6], 16),
    )


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name).lower()
