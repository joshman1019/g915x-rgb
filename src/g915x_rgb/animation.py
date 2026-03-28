"""Startup animations for the G915 X keyboard.

Each animation is a function that takes a G915XBackend, primary color,
and secondary color, then plays a visual effect before the profile
colors are applied.
"""

import math
import random
import time

from .backend import G915XBackend
from .keyboard_layout import G915X_KEYS

# --- Animation registry ---

ANIMATIONS: dict[str, tuple[str, callable]] = {}


def register(name: str, description: str):
    def decorator(func):
        ANIMATIONS[name] = (description, func)
        return func
    return decorator


def play_animation(name: str, kb: G915XBackend, profile=None) -> None:
    if name and name in ANIMATIONS:
        _, func = ANIMATIONS[name]
        primary = getattr(profile, 'animation_primary', (0, 128, 255)) if profile else (0, 128, 255)
        secondary = getattr(profile, 'animation_secondary', (255, 64, 128)) if profile else (255, 64, 128)
        func(kb, primary, secondary)


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


def _lerp(c1, c2, t):
    """Blend two RGB colors. t=0 gives c1, t=1 gives c2."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _dim(c, f):
    """Scale color brightness by factor f (0.0-1.0+)."""
    return (
        min(255, max(0, int(c[0] * f))),
        min(255, max(0, int(c[1] * f))),
        min(255, max(0, int(c[2] * f))),
    )


def _center():
    """Return (cx, cy) center of keyboard."""
    cx = sum(k.x + k.w / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    cy = sum(k.y + k.h / 2 for k in G915X_KEYS) / len(G915X_KEYS)
    return cx, cy


def _apply_frame(kb, new_frame, prev_frame):
    """Apply only the diff between frames for efficiency."""
    diff = {a: rgb for a, rgb in new_frame.items() if prev_frame.get(a) != rgb}
    if diff:
        kb.apply_key_colors(diff)
    return dict(new_frame)


# =====================================================================
# NEW CREATIVE ANIMATIONS
# =====================================================================

@register("aurora", "Aurora borealis — flowing curtains of light")
def anim_aurora(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)
    prev = {}
    for frame in range(45):
        t = frame * 0.15
        new_frame = {}
        for key in G915X_KEYS:
            kx = key.x + key.w / 2
            ky = key.y + key.h / 2
            # Y-based primary/secondary blend
            y_blend = max(0.0, min(1.0, (ky + 0.5) / 6.0))
            base = _lerp(primary, secondary, y_blend)
            # Two sine waves at different frequencies for shimmer
            wave1 = math.sin(kx * 0.4 + t) * 0.5 + 0.5
            wave2 = math.sin(kx * 0.7 - t * 1.3 + ky * 0.3) * 0.5 + 0.5
            brightness = wave1 * 0.6 + wave2 * 0.4
            # Extra shimmer
            shimmer = math.sin(kx * 1.5 + t * 3.0) * 0.15 + 0.85
            brightness *= shimmer
            new_frame[key.address] = _dim(base, brightness)
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.07)
    # Fade out
    for step in range(5, 0, -1):
        f = step / 5
        faded = {a: _dim(c, f) for a, c in prev.items()}
        prev = _apply_frame(kb, faded, prev)
        time.sleep(0.08)
    kb.set_all_keys(0, 0, 0)


@register("comet", "Twin comets — streaks of light crossing paths")
def anim_comet(kb: G915XBackend, primary, secondary) -> None:
    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())
    n = len(sorted_cols)
    trail = 6

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    prev = {}
    for frame in range(n + trail + 4):
        new_frame = {}
        for i, col_x in enumerate(sorted_cols):
            # Primary comet: left to right
            dist_p = frame - i
            # Secondary comet: right to left
            dist_s = frame - (n - 1 - i)

            color = OFF
            for d, col, base in [(dist_p, primary, 0), (dist_s, secondary, 0)]:
                if 0 <= d < trail:
                    brightness = 1.0 - d / trail
                    c = (255, 255, 255) if d == 0 else _dim(col, brightness)
                    if color == OFF:
                        color = c
                    else:
                        # Blend overlapping comets
                        color = _lerp(color, c, 0.5)

            for addr in columns[col_x]:
                new_frame[addr] = color

        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.055)

    kb.set_all_keys(0, 0, 0)


@register("ripple", "Concentric ripples — waves from the center")
def anim_ripple(kb: G915XBackend, primary, secondary) -> None:
    cx, cy = _center()
    max_d = max(((k.x + k.w/2 - cx)**2 + (k.y + k.h/2 - cy)**2)**0.5 for k in G915X_KEYS)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    ring_width = 2.0
    wave_speed = 0.8
    prev = {}
    for frame in range(40):
        t = frame * wave_speed
        new_frame = {}
        for key in G915X_KEYS:
            kx = key.x + key.w / 2
            ky = key.y + key.h / 2
            d = ((kx - cx)**2 + (ky - cy)**2)**0.5

            brightness = 0.0
            best_color = primary
            # Three waves, offset in time
            for wave_i in range(3):
                wave_front = t - wave_i * 3.0
                ring_dist = abs(d - wave_front)
                if ring_dist < ring_width:
                    b = (1.0 - ring_dist / ring_width) ** 2
                    if b > brightness:
                        brightness = b
                        best_color = primary if wave_i % 2 == 0 else secondary

            new_frame[key.address] = _dim(best_color, brightness) if brightness > 0.02 else OFF
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.07)
    kb.set_all_keys(0, 0, 0)


@register("helix", "Double helix — intertwined sine waves")
def anim_helix(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    cy = 3.0  # vertical center
    amplitude = 2.5
    prev = {}
    for frame in range(40):
        phase = frame * 0.25
        new_frame = {}
        for key in G915X_KEYS:
            kx = key.x + key.w / 2
            ky = key.y + key.h / 2
            # Two strands
            y1 = cy + amplitude * math.sin(kx * 0.5 + phase)
            y2 = cy + amplitude * math.sin(kx * 0.5 + phase + math.pi)
            d1 = abs(ky - y1)
            d2 = abs(ky - y2)
            b1 = max(0, 1.0 - d1 / 1.2) ** 2
            b2 = max(0, 1.0 - d2 / 1.2) ** 2

            if b1 > 0.02 and b2 > 0.02:
                # Crossover — blend to white
                blend = min(b1, b2) / max(b1, b2)
                color = _lerp(_lerp(primary, secondary, b2 / (b1 + b2)), (255, 255, 255), blend * 0.7)
                brightness = max(b1, b2)
            elif b1 > 0.02:
                color = primary
                brightness = b1
            elif b2 > 0.02:
                color = secondary
                brightness = b2
            else:
                color = OFF
                brightness = 0

            new_frame[key.address] = _dim(color, brightness) if brightness > 0.02 else OFF
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.07)
    kb.set_all_keys(0, 0, 0)


@register("prism", "Light prism — white beam splits into color spectrum")
def anim_prism(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    prism_x = 6.0  # prism point ~1/4 across
    max_x = max(k.x + k.w for k in G915X_KEYS)
    min_y = min(k.y for k in G915X_KEYS)
    max_y = max(k.y + k.h for k in G915X_KEYS)
    beam_y = 3.0  # center row

    prev = {}
    # Phase 1: white beam enters (12 frames)
    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())
    beam_cols = [c for c in sorted_cols if c <= prism_x]
    for frame in range(len(beam_cols)):
        new_frame = dict(prev)
        col_x = beam_cols[frame]
        for key in G915X_KEYS:
            kx = key.x + key.w / 2
            ky = key.y + key.h / 2
            if abs(kx - col_x) < 0.8 and abs(ky - beam_y) < 1.2:
                b = max(0, 1.0 - abs(ky - beam_y) / 1.2)
                new_frame[key.address] = _dim((255, 255, 255), b)
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.04)

    # Phase 2: fan out from prism (25 frames)
    for frame in range(25):
        reveal_x = prism_x + (frame / 24) * (max_x - prism_x)
        new_frame = dict(prev)
        for key in G915X_KEYS:
            kx = key.x + key.w / 2
            ky = key.y + key.h / 2
            if kx > prism_x and kx <= reveal_x:
                # Map Y position to primary-secondary blend
                y_norm = (ky - min_y) / (max_y - min_y)
                color = _lerp(primary, secondary, y_norm)
                # Brightness based on distance from prism
                dist = kx - prism_x
                b = min(1.0, 0.3 + dist / (max_x - prism_x) * 0.7)
                new_frame[key.address] = _dim(color, b)
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.06)

    time.sleep(0.4)
    # Fade out
    for step in range(5, 0, -1):
        f = step / 5
        faded = {a: _dim(c, f) for a, c in prev.items()}
        prev = _apply_frame(kb, faded, prev)
        time.sleep(0.08)
    kb.set_all_keys(0, 0, 0)


@register("pulse", "Breathing pulse — smooth color breathing")
def anim_pulse(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.1)

    # Two full breaths: primary then secondary
    for color in [primary, secondary, _lerp(primary, secondary, 0.5)]:
        for frame in range(20):
            t = frame / 19
            brightness = math.sin(t * math.pi)  # 0 → 1 → 0
            c = _dim(color, brightness)
            kb.set_all_keys(*c)
            time.sleep(0.055)
    kb.set_all_keys(0, 0, 0)


@register("cascade", "Waterfall cascade — color falls then pools upward")
def anim_cascade(kb: G915XBackend, primary, secondary) -> None:
    rows = _keys_by_row()
    sorted_rows = sorted(rows.keys())
    n_rows = len(sorted_rows)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    prev = {}
    # Phase 1: Primary falls from top
    for i in range(n_rows):
        new_frame = dict(prev)
        for j in range(i + 1):
            brightness = 1.0 - (i - j) * 0.15
            brightness = max(0.15, brightness)
            for addr in rows[sorted_rows[j]]:
                new_frame[addr] = _dim(primary, brightness)
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.12)

    time.sleep(0.15)

    # Phase 2: Secondary pools upward from bottom
    for i in range(n_rows):
        new_frame = dict(prev)
        row_idx = n_rows - 1 - i
        # Blend: rows below are secondary, rows above stay primary
        for j in range(n_rows):
            if j >= row_idx:
                blend = min(1.0, (j - row_idx + 1) / (n_rows - row_idx))
                color = _lerp(primary, secondary, blend)
            else:
                color = _dim(primary, 0.6)
            for addr in rows[sorted_rows[j]]:
                new_frame[addr] = color
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.12)

    time.sleep(0.2)
    # Fade out
    for step in range(5, 0, -1):
        f = step / 5
        faded = {a: _dim(c, f) for a, c in prev.items()}
        prev = _apply_frame(kb, faded, prev)
        time.sleep(0.08)
    kb.set_all_keys(0, 0, 0)


@register("vortex", "Spiral vortex — swirl from edges to center")
def anim_vortex(kb: G915XBackend, primary, secondary) -> None:
    cx, cy = _center()

    def spiral_key(k):
        dx = k.x + k.w / 2 - cx
        dy = k.y + k.h / 2 - cy
        angle = math.atan2(dy, dx)
        dist = (dx**2 + dy**2) ** 0.5
        return angle + dist * 0.5  # spiral ordering

    by_spiral = sorted(G915X_KEYS, key=spiral_key)
    max_d = max(((k.x + k.w/2 - cx)**2 + (k.y + k.h/2 - cy)**2)**0.5 for k in G915X_KEYS)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    # Spiral in: secondary at edges → primary at center
    chunk = max(len(by_spiral) // 25, 1)
    prev = {}
    for i in range(0, len(by_spiral), chunk):
        batch = by_spiral[i:i + chunk]
        new_frame = dict(prev)
        t = i / len(by_spiral)
        color = _lerp(secondary, primary, t)
        for key in batch:
            new_frame[key.address] = color
        prev = _apply_frame(kb, new_frame, prev)
        time.sleep(0.05)

    # Flash
    flash = _lerp(primary, (255, 255, 255), 0.5)
    kb.apply_key_colors({a: flash for a in ALL_KEYS})
    time.sleep(0.15)
    kb.apply_key_colors({a: primary for a in ALL_KEYS})
    time.sleep(0.2)

    # Fade out
    _fade(kb, ALL_KEYS, primary, steps=5, duration=0.5)


@register("lightning", "Electric storm — jagged bolts of light")
def anim_lightning(kb: G915XBackend, primary, secondary) -> None:
    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())
    rows = _keys_by_row()
    sorted_rows = sorted(rows.keys())

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    # Dim ambient glow
    ambient = _dim(secondary, 0.15)
    kb.apply_key_colors({a: ambient for a in ALL_KEYS})
    time.sleep(0.2)

    # 4 lightning bolts
    for bolt in range(4):
        # Generate jagged path: pick a starting column, zigzag down
        col_idx = random.randint(3, len(sorted_cols) - 4)
        bolt_keys = []
        for row_y in sorted_rows:
            col_idx = max(0, min(len(sorted_cols) - 1, col_idx + random.randint(-2, 2)))
            bolt_keys.extend(columns[sorted_cols[col_idx]])
            # Also light neighbors for thickness
            if col_idx > 0:
                bolt_keys.extend(columns[sorted_cols[col_idx - 1]])

        # Flash white
        flash_frame = {a: ambient for a in ALL_KEYS}
        for addr in bolt_keys:
            flash_frame[addr] = (255, 255, 255)
        kb.apply_key_colors(flash_frame)
        time.sleep(0.06)

        # Flash primary
        primary_frame = {a: ambient for a in ALL_KEYS}
        for addr in bolt_keys:
            primary_frame[addr] = primary
        kb.apply_key_colors(primary_frame)
        time.sleep(0.1)

        # Glow around bolt in secondary
        glow_frame = {a: ambient for a in ALL_KEYS}
        for addr in bolt_keys:
            glow_frame[addr] = _dim(primary, 0.4)
        kb.apply_key_colors(glow_frame)
        time.sleep(0.15)

        # Back to ambient
        kb.apply_key_colors({a: ambient for a in ALL_KEYS})
        time.sleep(random.uniform(0.15, 0.35))

    # Final flash — full keyboard
    kb.apply_key_colors({a: (255, 255, 255) for a in ALL_KEYS})
    time.sleep(0.08)
    kb.apply_key_colors({a: primary for a in ALL_KEYS})
    time.sleep(0.15)
    _fade(kb, ALL_KEYS, primary, steps=4, duration=0.4)


@register("tide", "Ocean tide — waves washing across")
def anim_tide(kb: G915XBackend, primary, secondary) -> None:
    max_x = max(k.x + k.w for k in G915X_KEYS)

    kb.set_all_keys(0, 0, 0)
    time.sleep(0.15)

    prev = {}
    # Two waves: primary then secondary
    for wave_i, wave_color in enumerate([primary, secondary]):
        speed = 0.8 if wave_i == 0 else 1.2
        for frame in range(30):
            wave_x = (frame / 29) * (max_x + 6) - 3
            new_frame = {}
            for key in G915X_KEYS:
                kx = key.x + key.w / 2
                ky = key.y + key.h / 2
                # Wave shape: sine modulated front
                wave_front = wave_x + math.sin(ky * 0.8) * 1.5
                dist = kx - wave_front

                if -1.5 < dist < 0:
                    # Foam crest (white)
                    b = 1.0 - abs(dist) / 1.5
                    new_frame[key.address] = _lerp(wave_color, (255, 255, 255), b * 0.7)
                elif -6 < dist < -1.5:
                    # Wave body
                    b = 1.0 - (abs(dist) - 1.5) / 4.5
                    new_frame[key.address] = _dim(wave_color, max(0.1, b))
                elif key.address in prev and prev[key.address] != OFF:
                    # Receding: dim what was there
                    new_frame[key.address] = _dim(prev.get(key.address, OFF), 0.85)
                else:
                    new_frame[key.address] = OFF

            prev = _apply_frame(kb, new_frame, prev)
            time.sleep(0.05)
        time.sleep(0.1)

    # Fade out
    for step in range(5, 0, -1):
        f = step / 5
        faded = {a: _dim(c, f) for a, c in prev.items()}
        prev = _apply_frame(kb, faded, prev)
        time.sleep(0.08)
    kb.set_all_keys(0, 0, 0)


# =====================================================================
# UPDATED GENERIC EFFECTS (with customizable colors)
# =====================================================================

@register("wave", "Color wave — sweeping left to right")
def anim_wave(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    columns = _keys_by_column()
    sorted_cols = sorted(columns.keys())

    trail_len = 5
    for i in range(len(sorted_cols) + trail_len + 2):
        for t in range(trail_len):
            col_idx = i - t
            if 0 <= col_idx < len(sorted_cols):
                col_x = sorted_cols[col_idx]
                blend = col_idx / max(len(sorted_cols) - 1, 1)
                base_color = _lerp(primary, secondary, blend)
                fade = 1.0 - (t / trail_len) * 0.7
                if t == 0:
                    color = (255, 255, 255)  # bright head
                else:
                    color = _dim(base_color, fade)
                _set_many(kb, columns[col_x], *color)

        clear_idx = i - trail_len
        if 0 <= clear_idx < len(sorted_cols):
            _set_many(kb, columns[sorted_cols[clear_idx]], *OFF)
        time.sleep(0.04)

    _set_many(kb, ALL_KEYS, *OFF)


@register("sparkle", "Sparkling keys — twinkling lights")
def anim_sparkle(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    palette = [
        primary, secondary,
        _lerp(primary, secondary, 0.5),
        _lerp(primary, (255, 255, 255), 0.5),
        _lerp(secondary, (255, 255, 255), 0.5),
        (255, 255, 255),
    ]

    active: dict[int, int] = {}
    for _ in range(60):
        for _ in range(random.randint(2, 5)):
            addr = random.choice(ALL_KEYS)
            if addr not in active:
                _sc(kb, addr, *random.choice(palette))
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


@register("explosion", "Burst — expanding rings from center")
def anim_explosion(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    cx, cy = _center()

    def dist(k):
        return ((k.x + k.w / 2 - cx) ** 2 + (k.y + k.h / 2 - cy) ** 2) ** 0.5

    by_dist = sorted(G915X_KEYS, key=dist)
    n_rings = 6
    chunk = max(len(by_dist) // n_rings, 1)

    for i in range(0, len(by_dist), max(chunk, 1)):
        batch = by_dist[i:i + chunk]
        t = min(i / max(len(by_dist) - 1, 1), 1.0)
        color = _lerp(primary, secondary, t)
        if t < 0.15:
            color = _lerp((255, 255, 255), primary, t / 0.15)
        for key in batch:
            _sc(kb, key.address, *color)
        time.sleep(0.08)

    time.sleep(0.3)

    for i in range(len(by_dist) - 1, -1, -max(chunk, 1)):
        batch = by_dist[max(i - chunk, 0):i + 1]
        for key in batch:
            _sc(kb, key.address, *OFF)
        time.sleep(0.04)
    time.sleep(0.15)


@register("matrix", "Digital rain — falling code drops")
def anim_matrix(kb: G915XBackend, primary, secondary) -> None:
    kb.set_all_keys(0, 0, 0)
    time.sleep(0.2)

    head_color = _lerp(primary, (255, 255, 255), 0.5)
    body_color = primary
    dim_body = _dim(primary, 0.5)

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
            # Occasional secondary drops
            use_secondary = hash(col_x) % 5 == 0
            h_color = _lerp(secondary, (255, 255, 255), 0.5) if use_secondary else head_color
            b_color = secondary if use_secondary else body_color
            d_color = _dim(secondary, 0.5) if use_secondary else dim_body

            if row_idx < len(col):
                _sc(kb, col[row_idx].address, *h_color)
                if row_idx > 0:
                    _sc(kb, col[row_idx - 1].address, *b_color)
                if row_idx > 1:
                    _sc(kb, col[row_idx - 2].address, *d_color)
                if row_idx > 3:
                    _sc(kb, col[row_idx - 4].address, *OFF)
                drops[col_x] = row_idx + 1
            else:
                for j in range(max(row_idx - 4, 0), len(col)):
                    _sc(kb, col[j].address, *OFF)
                finished.append(col_x)

        for col_x in finished:
            del drops[col_x]
        time.sleep(0.06)

    _set_many(kb, ALL_KEYS, *OFF)
