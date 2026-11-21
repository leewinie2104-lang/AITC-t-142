# Client rules (core — not scaffolded yet)

Loads for any file under `client/`. Decisions: ADR-0002 (React + Vite SPA on S3 + CloudFront) ·
ADR-0003 (REST + OpenAPI, SSE, WebSocket, single domain). Wireframes: `docs/01-product/ux/wireframes/`.

- React + TypeScript (strict) + Vite SPA, Tailwind + shadcn/ui, TanStack Query for server state.
- Talk to the API only via `/api/v1` (client generated from the server OpenAPI), SSE for chat streaming,
  WebSocket for realtime notifications. Same domain, no CORS workarounds.
- UI text is Vietnamese.
- Static build to S3 + CloudFront; no server-side rendering.

## When scaffolding

Write a plan first. Then keep this file as the FE core (commands, folder layout, lint/test) and add narrower
path-scoped files instead of growing it, for example:
- `client-ui.md` → `client/src/components/**`, `client/src/pages/**` (shadcn, a11y, Vietnamese copy)
- `client-api.md` → `client/src/api/**` (generated client, TanStack Query keys, SSE / WebSocket)
- `client-tests.md` → `client/**/*.test.*`, `client/e2e/**`
Follow `.claude/rules/rules-authoring.md` for each new file.
