import pytest

from yt_idea_collector.config import Config, REQUIRED


def test_config_requires_all_secrets(monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Missing required"):
        Config.from_env()


def test_config_parses_overrides(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, name.lower())
    monkeypatch.setenv("GEMINI_BATCH_SIZE", "7")
    monkeypatch.setenv("BACKFILL_START", "2025-12-01")
    config = Config.from_env(dry_run=True)
    assert config.batch_size == 7
    assert config.dry_run is True
    assert config.backfill_start.isoformat() == "2025-12-01"


def test_config_rejects_unsafe_batch(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("GEMINI_BATCH_SIZE", "51")
    with pytest.raises(ValueError, match="between 1 and 50"):
        Config.from_env()

