---
name: new-usecase
description: Scaffold a new use case in a ParkSmart backend module (ADR-0010) — domain entity/errors/port, use case with input DTO and execute(), optional REST endpoint and asyncpg repository, wiring in main_api.py, and a unit test with fake ports. Use when adding any business operation or REST endpoint under server/src/app/<module>/.
---

# New use case

Inputs: module (e.g. `booking`), operation name in `verb_noun` form (e.g. `hold_slot`), whether it needs
a REST endpoint and/or persistence, and the BR / AC it implements.

## Steps

1. **Read context**: `.claude/rules/backend.md` (module map, layer rules), the module's existing files, and the
   rules in `docs/01-product/prd.md` / acceptance criteria for this operation.
2. **Domain** (`server/src/app/<module>/domain/`, stdlib only):
   - `entity.py`: `@dataclass(frozen=True, slots=True)` entities/value objects.
   - `errors.py`: one exception class per business failure, subclass of a module base error.
   - `ports.py`: `typing.Protocol` for the repository and for any data owned by another module
     (e.g. `EligibilityChecker` in `booking`). Never import the other module.
3. **Use case** `server/src/app/<module>/usecase/<verb_noun>.py` — follow
   [templates/usecase.py.tmpl](templates/usecase.py.tmpl): `<Op>Input` dataclass, `<Op>` class taking ports
   in `__init__`, `async def execute(self, inp) -> <Result>`. Business decisions use `policy` results
   passed in via a port — never the LLM.
4. **REST** (if needed) `delivery/rest/schemas.py` (Pydantic v2 request/response) and `router.py` —
   [templates/router.py.tmpl](templates/router.py.tmpl). Map each domain error to an HTTP status. Prefix `/api/v1/<module>`.
5. **Persistence** (if needed): migration via skill `new-migration`, then
   `infrastructure/postgres/repository.py` implementing the port with asyncpg and `$n` parameters
   ([templates/repository.py.tmpl](templates/repository.py.tmpl)).
6. **Wire** in `server/src/app/main_api.py` (`create_app`): build repository → use case → include router.
   Cross-module ports are satisfied here by adapting the other module's use case.
7. **Test** `server/tests/unit/<module>/test_<verb_noun>.py` — [templates/test_usecase.py.tmpl](templates/test_usecase.py.tmpl):
   fake ports, happy path + every domain error + boundaries. Add an API test with the `client` fixture if
   there is an endpoint.
8. Remove `.gitkeep` from folders that now have files; keep it in still-empty ones.
9. Verify: `make check` and `python .claude/hooks/check_arch.py --all`.
