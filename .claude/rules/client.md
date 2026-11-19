---
paths:
  - "client/**"
---

# Client rules (not initialized)

The client is not scaffolded yet. When it is, follow
`docs/07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md` and
`docs/07-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md`:

- React + TypeScript (strict) + Vite SPA, Tailwind + shadcn/ui, TanStack Query for server state.
- Talk to the API only via `/api/v1` (REST, generated from the server OpenAPI), SSE for chat streaming,
  WebSocket for realtime notifications. Same domain — no CORS workarounds.
- UI text is Vietnamese. Low-fi wireframes: `docs/01-product/ux/wireframes/`.
- Hosting: static build to S3 + CloudFront; no server-side rendering.

Before scaffolding, write a plan in `.claude/plans/` and extend this file with commands, folder layout,
lint/test tooling, then add frontend skills/agents.
