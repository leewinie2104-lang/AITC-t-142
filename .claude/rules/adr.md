---
paths:
  - "docs/07-adr/**"
---

# ADR writing rules

- Keep every Markdown file in `docs/07-adr/` to **50 lines or fewer**. If a draft is longer, tighten it or link to a
  relevant document; do not exceed the limit.
- Each ADR states the **current** decision for one topic. Add same-topic detail by editing the live ADR; never write
  "partly superseded by" notes. A changed decision gets a new ADR and the old one becomes `Superseded by ADR-XXXX`.
- Two ADRs on the same topic are merged: keep one, turn the other into a short stub that links to it (keeps old links).
- Write in plain, concise Vietnamese that a teammate understands on first read; explain technical terms the first time.
- Keep only the context, decision, consequences, observability impact and alternatives needed to understand the choice.
