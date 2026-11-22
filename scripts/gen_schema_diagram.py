#!/usr/bin/env python3
"""Generate docs/03-design/diagrams/schema-diagram.html from docs/03-design/sql/schema.sql.

Run from the repo root after any schema change:
    python scripts/gen_schema_diagram.py

Stdlib only. Reads every `CREATE TABLE app.<name> (...)` block, its columns (type, NOT NULL, PK, UNIQUE, FK) and
table-level FOREIGN KEY clauses, groups tables by the numbered section header above them ("-- 8. Sharing (M4) ..."),
and writes one self-contained HTML page (cards per table, search, click a table to highlight its relations).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "docs" / "03-design" / "sql" / "schema.sql"
OUT = ROOT / "docs" / "03-design" / "diagrams" / "schema-diagram.html"

SECTION_RE = re.compile(r"^-- (\d+[a-z]?)\. (.+?)\s*$")
TABLE_RE = re.compile(r"CREATE TABLE app\.(\w+) \(")
STOP_WORDS = {
    "NOT",
    "NULL",
    "DEFAULT",
    "PRIMARY",
    "REFERENCES",
    "CHECK",
    "UNIQUE",
    "GENERATED",
    "CONSTRAINT",
    "COLLATE",
}
TABLE_CONSTRAINT = ("CONSTRAINT", "CHECK", "UNIQUE", "PRIMARY KEY", "FOREIGN KEY", "EXCLUDE")


def strip_comments(sql: str) -> str:
    """Drop `-- …` comments, ignoring `--` inside single-quoted strings."""
    out, quote, i = [], False, 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            quote = not quote
        if not quote and sql.startswith("--", i):
            while i < len(sql) and sql[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def short_title(title: str) -> str:
    """'8. Sharing (M4): owner publishes …' -> '8. Sharing (M4)'."""
    cut = min((i for sep in (":", " — ", ". ") if (i := title.find(sep, 4)) > 0), default=len(title))
    return title[:cut].strip()


def split_top_level(body: str) -> list[str]:
    parts, depth, cur, quote = [], 0, [], False
    for ch in body:
        if ch == "'":
            quote = not quote
        if not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def table_body(sql: str, start: int) -> str:
    depth, i = 0, start
    while i < len(sql):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return sql[start + 1 : i]
        i += 1
    raise ValueError("unbalanced CREATE TABLE")


def parse_column(item: str) -> dict:
    tokens = item.split()
    name, type_tokens = tokens[0], []
    for tok in tokens[1:]:
        if tok.upper() in STOP_WORDS:
            break
        type_tokens.append(tok)
    upper = item.upper()
    ref = re.search(r"REFERENCES app\.(\w+)", item)
    return {
        "name": name,
        "type": " ".join(type_tokens).replace("app.", ""),
        "nn": "NOT NULL" in upper or "PRIMARY KEY" in upper,
        "pk": "PRIMARY KEY" in upper,
        "uk": bool(re.search(r"\bUNIQUE\b", upper)),
        "fk": ref.group(1) if ref else None,
    }


def parse(sql: str) -> list[dict]:
    sections: list[tuple[int, str]] = []
    offset = 0
    for line in sql.splitlines(keepends=True):
        m = SECTION_RE.match(line.rstrip("\n"))
        if m:
            sections.append((offset, short_title(f"{m.group(1)}. {m.group(2)}")))
        offset += len(line)
    tables = []
    for m in TABLE_RE.finditer(sql):
        section = next((title for pos, title in reversed(sections) if pos < m.start()), "Khác")
        body = strip_comments(table_body(sql, m.end() - 1))
        columns, fks = [], set()
        for item in split_top_level(body):
            if not item:
                continue
            if item.upper().startswith(TABLE_CONSTRAINT):
                fk = re.search(r"FOREIGN KEY \(([^)]*)\)\s+REFERENCES app\.(\w+)", item)
                if fk:
                    for col in (c.strip() for c in fk.group(1).split(",")):
                        fks.add((col, fk.group(2)))
                continue
            columns.append(parse_column(item))
        for col in columns:
            for col_name, target in fks:
                if col["name"] == col_name and col_name != "zone_id" and not col["fk"]:
                    col["fk"] = target
            if col["name"] == "zone_id" and not col["fk"]:
                col["fk"] = "zone" if any(c == "zone_id" for c, _ in fks) or m.group(1) != "zone" else None
        tables.append({"name": m.group(1), "section": section, "columns": columns})
    return tables


def render(tables: list[dict], version: str) -> str:
    data = json.dumps(tables, ensure_ascii=False)
    return TEMPLATE.replace("__DATA__", data).replace("__VERSION__", version).replace("__COUNT__", str(len(tables)))


def main() -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    version = (re.search(r"^-- (v\d+) \(", sql, re.MULTILINE) or re.search(r"(v\d+)", sql)).group(1)
    tables = parse(sql)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(tables, version), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(tables)} tables ({version})")


TEMPLATE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sơ đồ schema ParkSmart</title>
<!-- Generated by scripts/gen_schema_diagram.py from docs/03-design/sql/schema.sql. Do not edit by hand. -->
<style>
:root { --bg:#f6f7f9; --card:#fff; --ink:#1f2430; --muted:#5b6475; --rule:#dde1e8; --pk:#1f2430; --fk:#2563eb;
        --hl:#fde68a; --rel:#dbeafe; --chip:#eef1f5; --font: system-ui, -apple-system, "Segoe UI", sans-serif;
        --mono: ui-monospace, SFMono-Regular, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#12151b; --card:#1b1f27; --ink:#e7eaf0;
        --muted:#9aa3b2; --rule:#2c323d; --pk:#e7eaf0; --fk:#7aa7ff; --hl:#5b4a12; --rel:#1d2d4a; --chip:#262b35; } }
:root[data-theme="dark"] { --bg:#12151b; --card:#1b1f27; --ink:#e7eaf0; --muted:#9aa3b2; --rule:#2c323d; --pk:#e7eaf0;
        --fk:#7aa7ff; --hl:#5b4a12; --rel:#1d2d4a; --chip:#262b35; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 var(--font); padding:24px 16px 48px; }
.wrap { max-width:1400px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 16px; }
.bar { display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; margin-bottom:16px; position:sticky; top:0;
       background:var(--bg); padding:8px 0; z-index:2; }
.bar input { font:inherit; padding:6px 10px; border:1px solid var(--rule); border-radius:6px; background:var(--card);
             color:var(--ink); min-width:240px; }
.bar button { font:inherit; padding:6px 10px; border:1px solid var(--rule); border-radius:6px; background:var(--card);
              color:var(--ink); cursor:pointer; }
.legend { color:var(--muted); font-size:12px; }
.legend b { font-family:var(--mono); font-weight:600; }
section { margin:20px 0 8px; }
section h2 { font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 8px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--rule); border-radius:8px; overflow:hidden; cursor:pointer; }
.card.sel { outline:3px solid var(--fk); }
.card.rel { background:var(--rel); }
.card.dim { opacity:.35; }
.card h3 { margin:0; padding:8px 12px; font:600 14px var(--mono); border-bottom:1px solid var(--rule); display:flex;
           justify-content:space-between; gap:8px; }
.card h3 small { font:400 11px var(--font); color:var(--muted); }
table { width:100%; border-collapse:collapse; font-size:12px; }
td { padding:3px 12px; border-top:1px solid var(--rule); vertical-align:top; }
tr:first-child td { border-top:0; }
td.n { font-family:var(--mono); word-break:break-all; }
td.t { color:var(--muted); font-family:var(--mono); text-align:right; word-break:break-all; }
.k { display:inline-block; font:600 9px var(--mono); padding:0 4px; border-radius:3px; background:var(--chip); margin-left:4px; }
.k.pk { background:var(--pk); color:var(--card); }
.k.fk { color:var(--fk); }
tr.match td { background:var(--hl); }
@media (max-width:480px) { .bar input { min-width:0; width:100%; } }
</style>
</head>
<body>
<div class="wrap">
  <h1>Sơ đồ schema ParkSmart (__VERSION__, __COUNT__ bảng)</h1>
  <p class="sub">Sinh tự động từ <code>docs/03-design/sql/schema.sql</code> bằng <code>python scripts/gen_schema_diagram.py</code>.
     Bấm một bảng để tô sáng các bảng nó tham chiếu và các bảng tham chiếu nó. Ràng buộc chi tiết: xem file SQL.</p>
  <div class="bar">
    <input id="q" type="search" placeholder="Tìm bảng hoặc cột…" aria-label="Tìm bảng hoặc cột">
    <button id="clear" type="button">Bỏ chọn</button>
    <span class="legend"><b>PK</b> khóa chính · <b>FK</b> khóa ngoại (→ bảng) · <b>UK</b> duy nhất · <b>NN</b> bắt buộc</span>
  </div>
  <div id="root"></div>
</div>
<script>
const TABLES = __DATA__;
const root = document.getElementById('root');
const bySection = {};
TABLES.forEach(t => (bySection[t.section] = bySection[t.section] || []).push(t));
const refs = {};
TABLES.forEach(t => { refs[t.name] = new Set(); });
TABLES.forEach(t => t.columns.forEach(c => { if (c.fk && refs[c.fk] && c.fk !== t.name) { refs[t.name].add(c.fk); refs[c.fk].add(t.name); } }));
const esc = s => String(s).replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
Object.entries(bySection).forEach(([title, tables]) => {
  const sec = document.createElement('section');
  sec.innerHTML = '<h2>' + esc(title) + '</h2><div class="grid"></div>';
  const grid = sec.querySelector('.grid');
  tables.forEach(t => {
    const card = document.createElement('div');
    card.className = 'card'; card.dataset.name = t.name; card.tabIndex = 0;
    const rows = t.columns.map(c => '<tr data-col="' + esc(c.name) + '"><td class="n">' + esc(c.name)
      + (c.pk ? '<span class="k pk">PK</span>' : '') + (c.fk ? '<span class="k fk">FK</span>' : '')
      + (c.uk ? '<span class="k">UK</span>' : '') + (c.nn && !c.pk ? '<span class="k">NN</span>' : '')
      + '</td><td class="t">' + esc(c.fk ? '→ ' + c.fk : c.type) + '</td></tr>').join('');
    card.innerHTML = '<h3>' + esc(t.name) + '<small>' + t.columns.length + ' cột</small></h3><table>' + rows + '</table>';
    card.addEventListener('click', () => select(t.name));
    card.addEventListener('keydown', e => { if (e.key === 'Enter') select(t.name); });
    grid.appendChild(card);
  });
  root.appendChild(sec);
});
function select(name) {
  document.querySelectorAll('.card').forEach(c => {
    c.classList.toggle('sel', c.dataset.name === name);
    c.classList.toggle('rel', refs[name].has(c.dataset.name));
    c.classList.toggle('dim', c.dataset.name !== name && !refs[name].has(c.dataset.name));
  });
}
document.getElementById('clear').addEventListener('click', () =>
  document.querySelectorAll('.card').forEach(c => c.classList.remove('sel', 'rel', 'dim')));
document.getElementById('q').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll('.card').forEach(card => {
    let hit = !q || card.dataset.name.includes(q);
    card.querySelectorAll('tr').forEach(tr => {
      const m = q && tr.dataset.col.includes(q); tr.classList.toggle('match', !!m); if (m) hit = true;
    });
    card.style.display = hit ? '' : 'none';
  });
  document.querySelectorAll('section').forEach(s => {
    s.style.display = [...s.querySelectorAll('.card')].some(c => c.style.display !== 'none') ? '' : 'none';
  });
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
