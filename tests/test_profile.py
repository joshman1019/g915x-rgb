"""Profile JSON round-trip and v1 -> v2 migration."""

from __future__ import annotations

from g915x_rgb.profile import (
    AnimationProfile,
    Profile,
    ReactiveProfile,
    duplicate_profile,
)


def test_v1_migrates_startup_into_animation_profile():
    v1 = {
        "name": "Old",
        "version": 1,
        "startup_animation": "aurora",
        "animation_primary": "00ff00",
        "animation_secondary": "ff00ff",
        "groups": {"keys": "ffffff"},
        "individual_keys": {"64": "808080"},   # decimal 64 == 0x40
    }
    p = Profile.from_dict(v1)
    assert p.name == "Old"
    assert p.startup.name == "aurora"
    assert p.startup.primary == (0, 255, 0)
    assert p.startup.secondary == (255, 0, 255)
    # Defaults populate ambient/reactive cleanly.
    assert p.ambient.name == ""
    assert p.reactive.effect == ""
    assert p.group_colors["keys"] == (255, 255, 255)
    assert p.key_colors[0x40] == (0x80, 0x80, 0x80)


def test_v2_round_trip_preserves_all_fields():
    p = Profile(
        name="New",
        startup=AnimationProfile(name="comet", primary=(1, 2, 3), secondary=(4, 5, 6)),
        ambient=AnimationProfile(
            name="aurora", primary=(7, 8, 9), secondary=(10, 11, 12),
            speed=1.5, intensity=0.8,
        ),
        reactive=ReactiveProfile(effect="glow", color=(255, 100, 50), intensity=1.2),
    )
    p.group_colors["keys"] = (200, 200, 200)
    p.key_colors[0x10] = (50, 60, 70)
    p2 = Profile.from_dict(p.to_dict())
    assert p2.name == "New"
    assert p2.startup.name == "comet"
    assert p2.startup.primary == (1, 2, 3)
    assert p2.ambient.name == "aurora"
    assert p2.ambient.speed == 1.5
    assert abs(p2.ambient.intensity - 0.8) < 1e-9
    assert p2.reactive.effect == "glow"
    assert p2.reactive.color == (255, 100, 50)
    assert abs(p2.reactive.intensity - 1.2) < 1e-9
    assert p2.group_colors["keys"] == (200, 200, 200)
    assert p2.key_colors[0x10] == (50, 60, 70)
    assert "gkey_actions" not in p2.to_dict()


def test_legacy_property_setters_still_work():
    p = Profile(name="X")
    p.startup_animation = "matrix"
    p.animation_primary = (10, 20, 30)
    p.animation_secondary = (40, 50, 60)
    assert p.startup.name == "matrix"
    assert p.startup.primary == (10, 20, 30)
    assert p.startup.secondary == (40, 50, 60)


def test_duplicate_profile_is_independent():
    a = Profile(name="A")
    a.group_colors["keys"] = (1, 2, 3)
    a.key_colors[0x40] = (10, 11, 12)
    b = duplicate_profile(a, "B")
    assert b.name == "B"
    b.group_colors["keys"] = (255, 255, 255)
    b.key_colors[0x40] = (0, 0, 0)
    # Mutations on the copy must not bleed back.
    assert a.group_colors["keys"] == (1, 2, 3)
    assert a.key_colors[0x40] == (10, 11, 12)


def test_atomic_save_and_rename_unlinks_old_file(tmp_path, monkeypatch):
    import g915x_rgb.profile as profile_mod
    monkeypatch.setattr(profile_mod, "PROFILES_DIR", tmp_path)

    p = Profile(name="First")
    path1 = p.save()
    assert path1.exists()
    p.name = "Renamed"
    path2 = p.save()
    assert path2.exists()
    assert not path1.exists(), "old file should have been removed on rename"
