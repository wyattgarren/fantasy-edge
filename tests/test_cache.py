from pathlib import Path

from data.cache import FileCache


def test_set_then_get_roundtrip(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "cache")
    cache.set("players", {"a": 1}, ttl_seconds=60)
    assert cache.get("players") == {"a": 1}


def test_missing_key_returns_none(tmp_path: Path) -> None:
    cache = FileCache(tmp_path / "cache")
    assert cache.get("missing") is None


def test_expired_entry_returns_none(tmp_path: Path) -> None:
    now = [0.0]
    cache = FileCache(tmp_path / "cache", clock=lambda: now[0])

    cache.set("players", "value", ttl_seconds=10)
    assert cache.get("players") == "value"

    now[0] = 10.0  # exactly at expiry
    assert cache.get("players") is None


def test_persists_across_instances(tmp_path: Path) -> None:
    dir_ = tmp_path / "cache"
    FileCache(dir_).set("players", [1, 2, 3], ttl_seconds=60)
    assert FileCache(dir_).get("players") == [1, 2, 3]
