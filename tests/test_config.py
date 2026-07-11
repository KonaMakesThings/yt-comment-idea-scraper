import pytest

from yt_idea_collector.config import Config, REQUIRED


def test_config_requires_all_secrets(monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    for name in ("GOOGLE_REFRESH_TOKEN", "YOUTUBE_REFRESH_TOKEN", "SHEETS_REFRESH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Missing required"):
        Config.from_env()


def test_config_parses_overrides(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, name.lower())
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "legacy-token")
    monkeypatch.setenv("GEMINI_BATCH_SIZE", "7")
    monkeypatch.setenv("BACKFILL_START", "2025-12-01")
    config = Config.from_env(dry_run=True)
    assert config.batch_size == 7
    assert config.dry_run is True
    assert config.backfill_start.isoformat() == "2025-12-01"
    assert config.youtube_refresh_token == "legacy-token"
    assert config.sheets_refresh_token == "legacy-token"
    assert config.youtube_api_key == "youtube_api_key"


def test_config_supports_separate_youtube_and_sheets_accounts(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, name.lower())
    monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "youtube-account")
    monkeypatch.setenv("SHEETS_REFRESH_TOKEN", "business-account")
    config = Config.from_env()
    assert config.youtube_refresh_token == "youtube-account"
    assert config.sheets_refresh_token == "business-account"


def test_config_migrates_retired_gemini_model(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "x")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    assert Config.from_env().gemini_model == "gemini-3.1-flash-lite"


def test_config_rejects_unsafe_batch(monkeypatch):
    for name in REQUIRED:
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "x")
    monkeypatch.setenv("GEMINI_BATCH_SIZE", "51")
    with pytest.raises(ValueError, match="between 1 and 50"):
        Config.from_env()
