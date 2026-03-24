"""Startup animations for the G915 X keyboard.

Each animation is a function that takes a G915XBackend and plays
a visual effect before the profile colors are applied.
"""

import random
import time

from .backend import G915XBackend
from .keyboard_layout import KEY_BY_NAME, G915X_KEYS

# --- Animation registry ---

ANIMATIONS: dict[str, tuple[str, callable]] = {}


def register(name: str, description: str):
    def decorator(func):
        ANIMATIONS[name] = (description, func)
        return func
    return decorator


def play_animation(name: str, kb: G915XBackend) -> None:
    if name and name in ANIMATIONS:
        _, func = ANIMATIONS[name]
        func(kb)


def get_animation_choices() -> list[tuple[str, str]]:
    return [(name, desc) for name, (desc, _) in ANIMATIONS.items()]


# --- Helpers ---

ALL_KEYS = [k.address for k in G915X_KEYS]
OFF = (0x00, 0x00, 0x00)


def _sc(kb, addr, r, g, b):
    """Set key color and commit."""
    kb.set_key_color(addr, r, g, b)
    kb.commit()


def _set_many(kb, addrs, r, g, b):
    """Set multiple keys to same color and commit after all."""
    for addr in addrs:
        kb.set_key_color(addr, r, g, b)
        kb.commit()


def _fade(kb, addrs, color, steps=4, duration=0.3):
    """Fade keys from color to off."""
    r, g, b = color
    dt = duration / steps
    for i in range(steps, 0, -1):
        f = i / steps
        for addr in addrs:
            kb.set_key_color(addr, int(r * f), int(g * f), int(b * f))
            kb.commit()
        time.sleep(dt)
    _set_many(kb, addrs, *OFF)


def _keys_by_column():
    columns: dict[float, list[int]] = {}
    for key in G915X_KEYS:
        col = round(key.x * 2) / 2
        columns.setdefault(col, []).append(key.address)
    return columns


def _keys_by_row():
    rows: dict[float, list[int]] = {}
    for key in G915X_KEYS:
        row_y = round(key.y * 2) / 2
        rows.setdefault(row_y, []).append(key.address)
    return rows


# =====================================================================
# DISTRO ANIMATIONS
# =====================================================================

@register("arch", "Arch Linux — logo trace + ARCH text")
def anim_arch(kb: G915XBackend) -> None:
    ARCH_BLUE = (0x17, 0x93, 0xD1)
    BRIGHT_BLUE = (0x40, 0xB0, 0xFF)
    WHITE = (0xFF, 0xFF, 0xFF)

    # Pyramid keys — left slope, right slope, base
    peak = [KEY_BY_NAME["0"].address]
    upper_l = [KEY_BY_NAME["O"].address]
    upper_r = [KEY_BY_NAME["P"].address]
    mid_l = [KEY_BY_NAME["K"].address]
    mid_r = [KEY_BY_NAME["L"].address]
    mid_c = [KEY_BY_NAME[";"].address]
    base_l = [KEY_BY_NAME["M"].address]
    base_r = [KEY_BY_NAME["/"].address]

    arch_text = [KEY_BY_NAME[k].address for k in ["A", "R", "C", "H"]]
    all_pyramid = peak + upper_l + upper_r + mid_l + [mid_c[0]] + mid_r + base_l + base_r

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.3)

    # Phase 1: Trace the logo — light descends from peak down both sides
    _set_many(kb, peak, *WHITE)
    time.sleep(0.35)

    _set_many(kb, upper_l + upper_r, *WHITE)
    _set_many(kb, peak, *ARCH_BLUE)  # peak transitions to blue as light moves down
    time.sleep(0.3)

    _set_many(kb, mid_l + mid_c + mid_r, *WHITE)
    _set_many(kb, upper_l + upper_r, *ARCH_BLUE)
    time.sleep(0.3)

    _set_many(kb, base_l + base_r, *WHITE)
    _set_many(kb, mid_l + mid_c + mid_r, *ARCH_BLUE)
    time.sleep(0.3)

    _set_many(kb, base_l + base_r, *ARCH_BLUE)
    time.sleep(0.2)

    # Phase 2: Pyramid pulses bright
    _set_many(kb, all_pyramid, *BRIGHT_BLUE)
    time.sleep(0.15)
    _set_many(kb, all_pyramid, *ARCH_BLUE)
    time.sleep(0.15)
    _set_many(kb, all_pyramid, *BRIGHT_BLUE)
    time.sleep(0.2)

    # Phase 3: ARCH text blazes in white underneath
    for addr in arch_text:
        _sc(kb, addr, *WHITE)
        time.sleep(0.15)
    time.sleep(0.4)

    # Phase 4: Everything pulses together
    all_anim = all_pyramid + arch_text
    _set_many(kb, all_anim, *BRIGHT_BLUE)
    time.sleep(0.2)
    _set_many(kb, all_anim, *WHITE)
    time.sleep(0.1)
    _set_many(kb, all_anim, *ARCH_BLUE)
    time.sleep(0.3)

    # Fade out
    _fade(kb, all_anim, ARCH_BLUE, steps=3, duration=0.3)


@register("ubuntu", "Ubuntu — orange ring burst")
def anim_ubuntu(kb: G915XBackend) -> None:
    ORANGE = (0xE9, 0x54, 0x20)
    WARM = (0xFF, 0x80, 0x40)
    WHITE = (0xFF, 0xFF, 0xFF)

    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)

    def dist(k):
        return ((k.x + k.w / 2 - cx) ** 2 + (k.y + k.h / 2 - cy) ** 2) ** 0.5

    by_dist = sorted(G915X_KEYS, key=dist)
    max_d = dist(by_dist[-1])

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Expanding ring — only the edge lights up, center stays dark (circle of friends)
    ring_width = max_d / 5
    for phase in range(8):
        ring_center = (phase / 7) * max_d
        for key in by_dist:
            d = dist(key)
            if abs(d - ring_center) < ring_width:
                intensity = 1.0 - abs(d - ring_center) / ring_width
                r = int(ORANGE[0] * intensity)
                g = int(ORANGE[1] * intensity)
                b = int(ORANGE[2] * intensity)
                _sc(kb, key.address, r, g, b)
            elif d < ring_center - ring_width:
                _sc(kb, key.address, *OFF)
        time.sleep(0.1)

    # Flash warm
    _set_many(kb, ALL_KEYS, *WARM)
    time.sleep(0.15)
    _set_many(kb, ALL_KEYS, *ORANGE)
    time.sleep(0.3)

    # Type UBUNTU
    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "UBUNTU":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.12)
    time.sleep(0.4)

    ubuntu_addrs = [KEY_BY_NAME[c].address for c in "UBUNTU" if c in KEY_BY_NAME]
    _fade(kb, ubuntu_addrs, WHITE, steps=3, duration=0.3)


@register("fedora", "Fedora — blue infinity sweep")
def anim_fedora(kb: G915XBackend) -> None:
    FEDORA_BLUE = (0x3C, 0x6E, 0xB4)
    FEDORA_DARK = (0x29, 0x4B, 0x7A)
    WHITE = (0xFF, 0xFF, 0xFF)

    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Sweep right in blue, then sweep left in dark blue (infinity loop feel)
    for col_x in sorted_cols:
        _set_many(kb, columns[col_x], *FEDORA_BLUE)
        time.sleep(0.025)
    time.sleep(0.1)

    for col_x in reversed(sorted_cols):
        _set_many(kb, columns[col_x], *FEDORA_DARK)
        time.sleep(0.025)
    time.sleep(0.1)

    for col_x in sorted_cols:
        _set_many(kb, columns[col_x], *WHITE)
        time.sleep(0.02)
    time.sleep(0.15)

    _set_many(kb, ALL_KEYS, *FEDORA_BLUE)
    time.sleep(0.2)

    # Type FEDORA
    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "FEDORA":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.1)
    time.sleep(0.4)

    fedora_addrs = [KEY_BY_NAME[c].address for c in "FEDORA" if c in KEY_BY_NAME]
    _fade(kb, fedora_addrs, WHITE, steps=3, duration=0.3)


@register("debian", "Debian — red spiral from center")
def anim_debian(kb: G915XBackend) -> None:
    DEBIAN_RED = (0xA8, 0x00, 0x30)
    BRIGHT_RED = (0xFF, 0x20, 0x50)
    WHITE = (0xFF, 0xFF, 0xFF)

    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)

    import math

    def angle_dist(k):
        dx = k.x + k.w / 2 - cx
        dy = k.y + k.h / 2 - cy
        angle = math.atan2(dy, dx)
        dist = (dx ** 2 + dy ** 2) ** 0.5
        return angle + dist * 0.3  # spiral: angle offset by distance

    by_spiral = sorted(G915X_KEYS, key=angle_dist)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Spiral outward in red
    chunk = max(len(by_spiral) // 20, 1)
    for i in range(0, len(by_spiral), chunk):
        for key in by_spiral[i:i + chunk]:
            _sc(kb, key.address, *DEBIAN_RED)
        time.sleep(0.05)

    time.sleep(0.15)
    _set_many(kb, ALL_KEYS, *BRIGHT_RED)
    time.sleep(0.15)
    _set_many(kb, ALL_KEYS, *DEBIAN_RED)
    time.sleep(0.2)

    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "DEBIAN":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.1)
    time.sleep(0.4)

    debian_addrs = [KEY_BY_NAME[c].address for c in "DEBIAN" if c in KEY_BY_NAME]
    _fade(kb, debian_addrs, WHITE, steps=3, duration=0.3)


@register("mint", "Linux Mint — green growth")
def anim_mint(kb: G915XBackend) -> None:
    MINT = (0x87, 0xCF, 0x3E)
    DARK_MINT = (0x50, 0x90, 0x20)
    WHITE = (0xFF, 0xFF, 0xFF)

    rows = _keys_by_row()
    sorted_rows = sorted(rows.keys(), reverse=True)  # bottom up = growing

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Grow from bottom up like a plant
    for i, row_y in enumerate(sorted_rows):
        shade = MINT if i % 2 == 0 else DARK_MINT
        for addr in rows[row_y]:
            _sc(kb, addr, *shade)
        time.sleep(0.15)

    time.sleep(0.2)

    # Bloom — flash bright
    _set_many(kb, ALL_KEYS, *WHITE)
    time.sleep(0.1)
    _set_many(kb, ALL_KEYS, *MINT)
    time.sleep(0.3)

    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "MINT":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.15)
    time.sleep(0.4)

    mint_addrs = [KEY_BY_NAME[c].address for c in "MINT" if c in KEY_BY_NAME]
    _fade(kb, mint_addrs, WHITE, steps=3, duration=0.3)


@register("suse", "openSUSE — green chameleon zigzag")
def anim_suse(kb: G915XBackend) -> None:
    SUSE_GREEN = (0x73, 0xBA, 0x25)
    BRIGHT_GREEN = (0xA0, 0xFF, 0x40)
    WHITE = (0xFF, 0xFF, 0xFF)

    rows = _keys_by_row()
    sorted_row_keys = sorted(rows.keys())

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Zigzag across rows — alternating left-to-right and right-to-left
    for i, row_y in enumerate(sorted_row_keys):
        addrs = sorted(rows[row_y])
        if i % 2 == 1:
            addrs = list(reversed(addrs))
        for addr in addrs:
            _sc(kb, addr, *SUSE_GREEN)
        time.sleep(0.1)

    _set_many(kb, ALL_KEYS, *BRIGHT_GREEN)
    time.sleep(0.15)
    _set_many(kb, ALL_KEYS, *SUSE_GREEN)
    time.sleep(0.3)

    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    # S-U-S-E
    for letter in ["S", "U", "S", "E"]:
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.15)
    time.sleep(0.4)
    suse_addrs = list(set(KEY_BY_NAME[c].address for c in "SUSE" if c in KEY_BY_NAME))
    _fade(kb, suse_addrs, WHITE, steps=3, duration=0.3)


@register("nix", "NixOS — blue snowflake expand")
def anim_nix(kb: G915XBackend) -> None:
    NIX_BLUE = (0x7E, 0xBA, 0xE4)
    NIX_DARK = (0x5A, 0x7F, 0xB0)
    WHITE = (0xFF, 0xFF, 0xFF)

    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)

    def dist(k):
        return ((k.x + k.w / 2 - cx) ** 2 + (k.y + k.h / 2 - cy) ** 2) ** 0.5

    by_dist = sorted(G915X_KEYS, key=dist)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # Snowflake: expand from center in alternating rings of color
    chunk = max(len(by_dist) // 10, 1)
    for i in range(0, len(by_dist), chunk):
        ring = by_dist[i:i + chunk]
        color = NIX_BLUE if (i // chunk) % 2 == 0 else NIX_DARK
        for key in ring:
            _sc(kb, key.address, *color)
        time.sleep(0.08)

    time.sleep(0.15)

    # Crystallize — flash white then settle
    _set_many(kb, ALL_KEYS, *WHITE)
    time.sleep(0.1)
    _set_many(kb, ALL_KEYS, *NIX_BLUE)
    time.sleep(0.2)

    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "NIX":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.15)
    time.sleep(0.4)

    nix_addrs = [KEY_BY_NAME[c].address for c in "NIX" if c in KEY_BY_NAME]
    _fade(kb, nix_addrs, WHITE, steps=3, duration=0.3)


@register("gentoo", "Gentoo — purple compile from nothing")
def anim_gentoo(kb: G915XBackend) -> None:
    GENTOO_PURPLE = (0x54, 0x48, 0x7A)
    GENTOO_LIGHT = (0x90, 0x70, 0xD0)
    WHITE = (0xFF, 0xFF, 0xFF)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    # "Compiling" — random keys flicker on like building from source
    build_order = list(G915X_KEYS)
    random.shuffle(build_order)

    for i, key in enumerate(build_order):
        # Flicker between purple shades as it "compiles"
        color = GENTOO_LIGHT if random.random() > 0.5 else GENTOO_PURPLE
        _sc(kb, key.address, *color)
        if i % 4 == 0:
            time.sleep(0.02)

    time.sleep(0.1)

    # "Build complete" — flash
    _set_many(kb, ALL_KEYS, *WHITE)
    time.sleep(0.1)
    _set_many(kb, ALL_KEYS, *GENTOO_PURPLE)
    time.sleep(0.3)

    _set_many(kb, ALL_KEYS, *OFF)
    time.sleep(0.1)
    for letter in "GENTOO":
        if letter in KEY_BY_NAME:
            _sc(kb, KEY_BY_NAME[letter].address, *WHITE)
            time.sleep(0.1)
    time.sleep(0.4)

    gentoo_addrs = [KEY_BY_NAME[c].address for c in "GENTOO" if c in KEY_BY_NAME]
    _fade(kb, gentoo_addrs, WHITE, steps=3, duration=0.3)


# =====================================================================
# GENERIC FUN EFFECTS
# =====================================================================

@register("wave", "Rainbow wave left to right")
def anim_wave(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())
    colors = [
        (0xFF, 0x00, 0x40), (0xFF, 0x40, 0x00), (0xFF, 0xC0, 0x00),
        (0x00, 0xFF, 0x40), (0x00, 0x80, 0xFF), (0x80, 0x00, 0xFF),
    ]

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
                _set_many(kb, columns[col_x], r, g, b)

        clear_idx = i - trail_len
        if 0 <= clear_idx < len(sorted_cols):
            _set_many(kb, columns[sorted_cols[clear_idx]], *OFF)
        time.sleep(0.04)

    _set_many(kb, ALL_KEYS, *OFF)


@register("sparkle", "Random sparkling keys")
def anim_sparkle(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    colors = [
        (0xFF, 0xFF, 0xFF), (0x80, 0xC0, 0xFF), (0xFF, 0x80, 0xC0),
        (0xC0, 0xFF, 0x80), (0xFF, 0xC0, 0x40), (0x80, 0x80, 0xFF),
    ]

    active: dict[int, int] = {}
    for _ in range(60):
        for _ in range(random.randint(2, 5)):
            addr = random.choice(ALL_KEYS)
            if addr not in active:
                _sc(kb, addr, *random.choice(colors))
                active[addr] = random.randint(2, 5)

        to_remove = []
        for addr, ticks in active.items():
            if ticks <= 1:
                _sc(kb, addr, *OFF)
                to_remove.append(addr)
            else:
                active[addr] = ticks - 1

        for addr in to_remove:
            del active[addr]
        time.sleep(0.05)

    for addr in list(active):
        _sc(kb, addr, *OFF)


@register("explosion", "Burst outward from center")
def anim_explosion(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)

    def dist(k):
        return ((k.x + k.w / 2 - cx) ** 2 + (k.y + k.h / 2 - cy) ** 2) ** 0.5

    by_dist = sorted(G915X_KEYS, key=dist)
    colors = [
        (0xFF, 0xFF, 0xFF), (0xFF, 0xFF, 0x60), (0xFF, 0x80, 0x00),
        (0xFF, 0x30, 0x00), (0xFF, 0x00, 0x00), (0x80, 0x00, 0x00),
    ]

    chunk = max(len(by_dist) // 6, 1)
    for i in range(0, len(by_dist), max(chunk, 1)):
        batch = by_dist[i:i + chunk]
        ci = min(i // max(chunk, 1), len(colors) - 1)
        for key in batch:
            _sc(kb, key.address, *colors[ci])
        time.sleep(0.08)

    time.sleep(0.3)

    for i in range(len(by_dist) - 1, -1, -max(chunk, 1)):
        batch = by_dist[max(i - chunk, 0):i + 1]
        for key in batch:
            _sc(kb, key.address, *OFF)
        time.sleep(0.04)
    time.sleep(0.15)


@register("matrix", "Green falling code")
def anim_matrix(kb: G915XBackend) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    columns: dict[float, list] = {}
    for key in G915X_KEYS:
        col = round(key.x * 2) / 2
        columns.setdefault(col, []).append(key)
    for col in columns.values():
        col.sort(key=lambda k: k.y)

    col_keys = sorted(columns.keys())
    drops: dict[float, int] = {}

    for tick in range(50):
        if random.random() < 0.4:
            col_x = random.choice(col_keys)
            if col_x not in drops:
                drops[col_x] = 0

        finished = []
        for col_x, row_idx in drops.items():
            col = columns[col_x]
            if row_idx < len(col):
                _sc(kb, col[row_idx].address, 0x80, 0xFF, 0x80)
                if row_idx > 0:
                    _sc(kb, col[row_idx - 1].address, 0x00, 0x80, 0x00)
                if row_idx > 2:
                    _sc(kb, col[row_idx - 3].address, *OFF)
                drops[col_x] = row_idx + 1
            else:
                for j in range(max(row_idx - 3, 0), len(col)):
                    _sc(kb, col[j].address, *OFF)
                finished.append(col_x)

        for col_x in finished:
            del drops[col_x]
        time.sleep(0.06)

    _set_many(kb, ALL_KEYS, *OFF)
