import pytest

from app.platform.prompts.loader import build_system_prompt, load_prompt, render


def test_render_replaces_placeholders():
    assert render("Xin chào {{name}}", name="BQL") == "Xin chào BQL"


def test_system_prompt_has_no_unrendered_placeholder():
    prompt = build_system_prompt()
    assert "{{shared_rules}}" not in prompt
    assert "{{safeguards}}" not in prompt


def test_missing_prompt_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("khong-ton-tai.md")
