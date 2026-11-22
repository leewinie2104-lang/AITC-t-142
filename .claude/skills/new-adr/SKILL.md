---
name: new-adr
description: Write a new Architecture Decision Record for ParkSmart in docs/07-adr (next ADR-NNNN number, Vietnamese content matching existing ADRs) and register it in docs/README.md. Use when choosing a library, changing architecture, data model strategy, infra or LLM usage, or superseding an existing ADR.
---

# New ADR

1. Next number: highest `docs/07-adr/ADR-NNNN-*.md` + 1. Filename `ADR-NNNN-<kebab-case-title>.md`.
2. Match the existing ADR format (read ADR-0010 as reference) — content in Vietnamese like the others:
   ```markdown
   # ADR-NNNN: <Title>

   - **Status**: Proposed | Accepted | Superseded by ADR-XXXX
   - **Date**: YYYY-MM-DD
   - **Liên quan**: <links to backlog, PRD sections, related ADRs>

   ## Context
   ## Decision
   ## Consequences
   ## Observability Impact
   ## Alternatives considered   (if needed)
   ## Cần xác nhận   (open questions, if any)
   ```
3. **50 lines max** per file (`.claude/rules/adr.md`). Include security impact when relevant (PII, RLS, cost).
4. Before writing, check whether a live ADR already covers the topic: if so, extend that ADR instead of adding one.
   Never change the decision of an Accepted ADR; supersede it and update the old one's Status line only.
5. Add the ADR to `docs/07-adr/README.md`, `docs/README.md` and link it from affected docs (`docs/02-architecture/02-tech-stack.md`,
   `docs/04-development/01-server-structure.md`) and, if it changes an invariant, from `.claude/rules/core.md`.
6. Run `python scripts/check_docs.py`.
