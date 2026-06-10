"""fetch_cache.FetchCache: TTL semantics, persistence, memory-only mode."""
import json
from datetime import datetime, timedelta, timezone

from pipeline.fetch_cache import FetchCache


def test_set_get_roundtrip(tmp_path):
    c = FetchCache(tmp_path / "c.json")
    c.set("k", {"a": 1})
    assert c.get("k", ttl_days=7) == {"a": 1}


def test_missing_key_returns_none(tmp_path):
    assert FetchCache(tmp_path / "c.json").get("nope", ttl_days=7) is None


def test_expired_entry_returns_none(tmp_path):
    c = FetchCache(tmp_path / "c.json")
    c.set("k", "v")
    old = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()
    c._data["k"]["ts"] = old
    assert c.get("k", ttl_days=7) is None
    assert c.get("k", ttl_days=30) == "v"   # same entry, looser TTL


def test_persists_across_instances(tmp_path):
    p = tmp_path / "c.json"
    FetchCache(p).set("k", [1, 2, 3]) or FetchCache(p)  # set then drop
    c1 = FetchCache(p); c1.set("k", [1, 2, 3]); c1.save()
    assert FetchCache(p).get("k", ttl_days=7) == [1, 2, 3]


def test_memory_only_when_path_none(tmp_path):
    c = FetchCache(None)
    c.set("k", "v"); c.save()  # save is a no-op
    assert c.get("k", ttl_days=7) == "v"


def test_corrupt_file_starts_empty(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ not json", encoding="utf-8")
    assert FetchCache(p).get("k", ttl_days=7) is None
