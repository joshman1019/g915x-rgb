"""Startup animations for the G915 X keyboard.

Each animation is a function that takes a G915XBackend and plays
a visual effect before the profile colors are applied.
"""

import random
import time

from .backend import G915XBackend
from .keyboard_layout import KEY_BY_NAME, G915X_KEYS

# --- Animation registry ---

ANIMATIONS: dict[str, tuple[str, callable]] = {}  # name -> (description, func)


def register(name: str, description: str):
    """Decorator to register an animation."""
    def decorator(func):
        ANIMATIONS[name] = (description, func)
        return func
    return decorator


def play_animation(name: str, kb: G915XBackend) -> None:
    """Play a named animation. No-op if name is empty or unknown."""
    if name and name in ANIMATIONS:
        _, func = ANIMATIONS[name]
        func(kb)


def get_animation_choices() -> list[tuple[str, str]]:
    """Return list of (name, description) for all registered animations."""
    return [(name, desc) for name, (desc, _) in ANIMATIONS.items()]


# --- Helper data ---

WHITE = (0xFF, 0xFF, 0xFF)
BLUE = (0x30, 0x80, 0xFF)
BRIGHT_BLUE = (0x60, 0xB0, 0xFF)
OFF = (0x00, 0x00, 0x00)

ALL_KEYS = [k.address for k in G915X_KEYS]
KEYS_BY_X = sorted(G915X_KEYS, key=lambda k: k.x)
KEYS_BY_Y = sorted(G915X_KEYS, key=lambda k: k.y)


def _set_and_commit(kb, addr, r, g, b):
    kb.set_key_color(addr, r, g, b)
    kb.commit()


# === ANIMATIONS ===


@register("arch", "ARCH text + pyramid logo")
def anim_arch(kb: G915XBackend) -> None:
    arch_keys = [KEY_BY_NAME[k].address for k in ["A", "R", "C", "H"]]
    pyramid_rows = [
        [KEY_BY_NAME[k].address for k in ["M", "/"]],
        [KEY_BY_NAME[k].address for k in ["K", ";", "L"]],
        [KEY_BY_NAME[k].address for k in ["O", "P"]],
        [KEY_BY_NAME[k].address for k in ["0"]],
    ]
    all_pyramid = [a for row in pyramid_rows for a in row]
    all_anim = arch_keys + all_pyramid

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.3)

    for letter, row in zip(arch_keys, pyramid_rows):
        _set_and_commit(kb, letter, *WHITE)
        for addr in row:
            _set_and_commit(kb, addr, *WHITE)
        time.sleep(0.5)

    time.sleep(0.3)

    for addr in all_anim:
        _set_and_commit(kb, addr, *BLUE)
    time.sleep(0.4)

    for addr in all_anim:
        _set_and_commit(kb, addr, *BRIGHT_BLUE)
    time.sleep(0.3)

    for addr in all_anim:
        _set_and_commit(kb, addr, *OFF)
    time.sleep(0.2)


@register("wave", "Color wave left to right")
def anim_wave(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Group keys into columns by X position
    columns: dict[float, list[int]] = {}
    for key in G915X_KEYS:
        col = round(key.x * 2) / 2  # snap to 0.5u grid
        columns.setdefault(col, []).append(key.address)

    sorted_cols = sorted(columns.keys())
    colors = [
        (0xFF, 0x00, 0x40),  # hot pink
        (0xFF, 0x40, 0x00),  # orange
        (0xFF, 0xC0, 0x00),  # gold
        (0x00, 0xFF, 0x40),  # green
        (0x00, 0x80, 0xFF),  # blue
        (0x80, 0x00, 0xFF),  # purple
    ]

    # Sweep a color wave across the keyboard
    trail_len = 4
    for i in range(len(sorted_cols) + trail_len + 2):
        for t in range(trail_len):
            col_idx = i - t
            if 0 <= col_idx < len(sorted_cols):
                col_x = sorted_cols[col_idx]
                color = colors[(i - t) % len(colors)]
                fade = 1.0 - (t / trail_len) * 0.7
                r = int(color[0] * fade)
                g = int(color[1] * fade)
                b = int(color[2] * fade)
                for addr in columns[col_x]:
                    _set_and_commit(kb, addr, r, g, b)

        # Clear the column that just left the trail
        clear_idx = i - trail_len
        if 0 <= clear_idx < len(sorted_cols):
            col_x = sorted_cols[clear_idx]
            for addr in columns[col_x]:
                _set_and_commit(kb, addr, *OFF)

        time.sleep(0.04)

    # Clear any remaining
    for addr in ALL_KEYS:
        _set_and_commit(kb, addr, *OFF)


@register("sparkle", "Random sparkling keys")
def anim_sparkle(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    colors = [
        (0xFF, 0xFF, 0xFF),
        (0x80, 0xC0, 0xFF),
        (0xFF, 0x80, 0xC0),
        (0xC0, 0xFF, 0x80),
        (0xFF, 0xC0, 0x40),
        (0x80, 0x80, 0xFF),
    ]

    active: dict[int, int] = {}  # addr -> ticks remaining
    for _ in range(60):
        # Spawn new sparkles
        for _ in range(random.randint(2, 5)):
            addr = random.choice(ALL_KEYS)
            if addr not in active:
                color = random.choice(colors)
                _set_and_commit(kb, addr, *color)
                active[addr] = random.randint(2, 5)

        # Decay existing sparkles
        to_remove = []
        for addr, ticks in active.items():
            if ticks <= 1:
                _set_and_commit(kb, addr, *OFF)
                to_remove.append(addr)
            else:
                active[addr] = ticks - 1

        for addr in to_remove:
            del active[addr]

        time.sleep(0.05)

    for addr in list(active):
        _set_and_commit(kb, addr, *OFF)


@register("cascade", "Top-to-bottom color cascade")
def anim_cascade(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Group keys by row (Y position)
    rows: dict[float, list[int]] = {}
    for key in G915X_KEYS:
        row_y = round(key.y * 2) / 2
        rows.setdefault(row_y, []).append(key.address)

    sorted_rows = sorted(rows.keys())
    colors = [
        (0x00, 0xFF, 0xFF),  # cyan
        (0x00, 0xC0, 0xFF),  # light blue
        (0x00, 0x80, 0xFF),  # blue
        (0x40, 0x40, 0xFF),  # indigo
        (0x80, 0x00, 0xFF),  # violet
        (0xC0, 0x00, 0xFF),  # purple
    ]

    # Drop each row with a trailing fade
    for i, row_y in enumerate(sorted_rows):
        color = colors[i % len(colors)]
        for addr in rows[row_y]:
            _set_and_commit(kb, addr, *color)
        time.sleep(0.15)

    time.sleep(0.5)

    # Flash bright white
    for addr in ALL_KEYS:
        _set_and_commit(kb, addr, 0xFF, 0xFF, 0xFF)
    time.sleep(0.15)

    # Fade out row by row top to bottom
    for row_y in sorted_rows:
        for addr in rows[row_y]:
            _set_and_commit(kb, addr, *OFF)
        time.sleep(0.08)

    time.sleep(0.15)


@register("explosion", "Burst outward from center")
def anim_explosion(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Center of the keyboard
    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)

    # Sort keys by distance from center
    def dist(k):
        return ((k.x + k.w / 2 - cx) ** 2 + (k.y + k.h / 2 - cy) ** 2) ** 0.5

    by_dist = sorted(G915X_KEYS, key=dist)
    max_dist = dist(by_dist[-1])

    # Explode outward in rings
    colors = [
        (0xFF, 0xFF, 0xFF),  # white core
        (0xFF, 0xFF, 0x60),  # yellow
        (0xFF, 0x80, 0x00),  # orange
        (0xFF, 0x30, 0x00),  # red-orange
        (0xFF, 0x00, 0x00),  # red
        (0x80, 0x00, 0x00),  # dark red
    ]

    chunk_size = len(by_dist) // 6
    for i in range(0, len(by_dist), max(chunk_size, 1)):
        chunk = by_dist[i:i + chunk_size]
        color_idx = min(i // max(chunk_size, 1), len(colors) - 1)
        for key in chunk:
            _set_and_commit(kb, key.address, *colors[color_idx])
        time.sleep(0.08)

    time.sleep(0.3)

    # Implode back (reverse order, fading out)
    for i in range(len(by_dist) - 1, -1, -max(chunk_size, 1)):
        chunk = by_dist[max(i - chunk_size, 0):i + 1]
        for key in chunk:
            _set_and_commit(kb, key.address, *OFF)
        time.sleep(0.04)

    time.sleep(0.15)


@register("matrix", "Green falling code")
def anim_matrix(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Group keys into columns
    columns: dict[float, list] = {}
    for key in G915X_KEYS:
        col = round(key.x * 2) / 2
        columns.setdefault(col, []).append(key)

    # Sort each column top-to-bottom
    for col in columns.values():
        col.sort(key=lambda k: k.y)

    col_keys = sorted(columns.keys())
    drops: dict[float, int] = {}  # col_x -> current row index

    for tick in range(50):
        # Spawn new drops
        if random.random() < 0.4:
            col_x = random.choice(col_keys)
            if col_x not in drops:
                drops[col_x] = 0

        # Advance drops
        finished = []
        for col_x, row_idx in drops.items():
            col = columns[col_x]
            if row_idx < len(col):
                # Bright head
                key = col[row_idx]
                _set_and_commit(kb, key.address, 0x80, 0xFF, 0x80)

                # Dim trail
                if row_idx > 0 and row_idx - 1 < len(col):
                    prev = col[row_idx - 1]
                    _set_and_commit(kb, prev.address, 0x00, 0x80, 0x00)
                if row_idx > 2 and row_idx - 3 < len(col):
                    old = col[row_idx - 3]
                    _set_and_commit(kb, old.address, *OFF)

                drops[col_x] = row_idx + 1
            else:
                # Clear trail
                for j in range(max(row_idx - 3, 0), len(col)):
                    _set_and_commit(kb, col[j].address, *OFF)
                finished.append(col_x)

        for col_x in finished:
            del drops[col_x]

        time.sleep(0.06)

    # Final cleanup
    for addr in ALL_KEYS:
        _set_and_commit(kb, addr, *OFF)
