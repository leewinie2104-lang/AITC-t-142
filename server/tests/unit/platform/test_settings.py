from app.platform.config.settings import Settings


def test_default_judge_differs_from_generate():
    settings = Settings(_env_file=None)
    assert settings.model_judge != settings.model_generate


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    assert Settings(_env_file=None).app_env == "test"
