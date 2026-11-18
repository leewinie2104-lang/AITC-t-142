---
name: new-adr
description: Write a new Architecture Decision Record for ParkSmart in docs/10-adr (next ADR-NNNN number, Vietnamese content matching existing ADRs) and register it in docs/README.md. Use when choosing a library, changing architecture, data model strategy, infra or LLM usage, or superseding an existing ADR.
---

# New ADR

1. Next number: highest `docs/10-adr/ADR-NNNN-*.md` + 1. Filename `ADR-NNNN-<kebab-case-title>.md`.
2. Match the existing ADR format (read ADR-0010 as reference) — content in Vietnamese like the others:
   ```markdown
   # ADR-NNNN: <Title>

   - **Status**: Proposed | Accepted | Superseded by ADR-XXXX
   - **Date**: YYYY-MM-DD
   - **Liên quan**: <links to backlog, PRD sections, related ADRs>

   ## Context
   ## Decision
   ## Consequences
   ## Alternatives considered
   ## Cần xác nhận   (open questions, if any)
   ```
3. Include observability and security impact when relevant (spans, PII, RLS, cost).
4. Never change the decision of an Accepted ADR; supersede it and update the old one's Status line only.
5. Add the ADR to `docs/README.md` and link it from affected docs (`docs/02-architecture/02-tech-stack.md`,
   `docs/05-development/01-server-structure.md`) and, if it changes an invariant, from `AGENTS.md`.
6. Run `python scripts/check_docs.py`.
