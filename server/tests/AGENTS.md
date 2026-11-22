# Backend rules — tests

Loads on top of `server/AGENTS.md`. Agent: `test-writer`.

- `tests/unit/<module>/test_<usecase>.py`: fake ports (in-memory classes or `AsyncMock`), no DB / LLM / network.
- `tests/unit/agent/`: patch `get_llm`; never call a real model.
- `tests/integration/`: real Postgres (`docker compose up postgres`), marked `@pytest.mark.integration`.
- API tests use the `client` fixture in `tests/conftest.py`; `asyncio_mode = auto`, `pythonpath = src`.
- Rule tables (L1–L4 × open scope × TH1/TH2/TH3) use `@pytest.mark.parametrize` with readable ids.
