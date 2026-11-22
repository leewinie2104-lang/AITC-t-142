#!/usr/bin/env python3
"""Generate docs/03-design/diagrams/tables.html: the interactive data dictionary of every table in schema.sql.

Run from the repo root after any schema change:
    python scripts/gen_tables_html.py

Stdlib only, deterministic. Reads docs/03-design/sql/schema.sql and writes one self-contained HTML page:
tables grouped like docs/03-design/dictionary/01…09, one card per table (columns with type, NOT NULL, DEFAULT,
FK target and the trailing SQL comment as note; table-level constraints; indexes; RLS policies; column grants).
Plan 024 additions are listed in NEW_TABLES / NEW_COLS / CHANGED_COLS below and shown as badges ("mới" / "đổi").
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "docs" / "03-design" / "sql" / "schema.sql"
OUT = ROOT / "docs" / "03-design" / "diagrams" / "tables.html"

# Same groups as docs/03-design/dictionary/01…09 (order matters).
GROUPS = [
    ("01", "Cơ sở vật chất và pool (M2, M3)", ["zone", "building", "slot_pool", "slot"]),
    ("02", "Tài khoản, nội quy (M1, M3)", ["app_user", "vehicle", "zone_policy"]),
    ("03", "Tư cách và đăng ký BQL (M1)", ["asset", "eligibility", "slot_holding", "bql_registry_import"]),
    ("04", "Chia sẻ, yêu cầu (M4, M5)", ["share_window", "parking_request"]),
    ("05", "Đặt chỗ, chủ về sớm (M5, M9)", ["booking", "recovery_case"]),
    ("06", "Thỏa thuận, thanh toán (M6, M7)", ["agreement", "consent_record", "payment"]),
    ("07", "Vận hành (M8, M12, M13)", ["lpr_event", "approval_request", "notification"]),
    ("08", "Agent, tri thức (M14, W7)", ["agent_thread", "ai_decision_log", "knowledge_chunk"]),
    ("09", "Tranh chấp (M10, W5)", ["dispute_case", "dispute_evidence"]),
]

# Plan 024 (2026-11-22) additions, written by hand so the badges do not depend on git history.
NEW_TABLES = {"bql_registry_import"}
NEW_COLS = {
    ("share_window", "owner_otp_confirmed_at"),
    ("share_window", "expires_at"),
    ("parking_request", "last_eta_minutes"),
    ("parking_request", "last_eta_at"),
    ("parking_request", "eta_source"),
    ("parking_request", "gps_consent_id"),
    ("parking_request", "gps_missed_streak"),
    ("parking_request", "is_urban_related"),
    ("booking", "assigned_at"),
    ("booking", "renter_otp_confirmed_at"),
    ("booking", "no_show_fee_vnd"),
    ("approval_request", "rule_result"),
    ("approval_request", "ai_risk"),
    ("approval_request", "reasons"),
    ("approval_request", "escalated_at"),
    ("approval_request", "bql_deadline_at"),
    ("approval_request", "bql_decision"),
    ("zone_policy", "hold_after_eta"),
    ("zone_policy", "hold_max"),
    ("zone_policy", "th3_hold_max"),
    ("zone_policy", "otp_confirm_ttl"),
    ("zone_policy", "listing_expiry"),
    ("zone_policy", "eta_assign_max"),
    ("zone_policy", "gps_interval"),
    ("zone_policy", "bql_review_ttl"),
    ("zone_policy", "no_show_fee_rate"),
    ("zone_policy", "no_show_min_hours"),
    ("zone_policy", "th3_guest_alert_slots"),
}
CHANGED_COLS = {
    ("parking_request", "queue_status"): "đổi giá trị: waiting/matched → queued…parked",
    ("recovery_case", "eta_source"): "đổi giá trị: location → gps",
    ("consent_record", "action"): "thêm owner_listing_otp, renter_assignment_otp",
    ("consent_record", "subject_type"): "thêm share_window, booking, parking_request",
    ("approval_request", "kind"): "thêm booking_review, registration_review",
}
REMOVED_COLS = {
    "zone_policy": ["hold_ttl → hold_after_eta (v7)"],
    "approval_request": ["due_at → bql_deadline_at (v7)"],
}

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


def squash(text: str) -> str:
    return " ".join(text.split())


def split_comments(lines: list[str]) -> tuple[str, dict[int, str]]:
    """Return the SQL without `--` comments (same line count) and {line index: comment text}."""
    code_lines, comments = [], {}
    for idx, line in enumerate(lines):
        quote, cut, i = False, None, 0
        while i < len(line):
            if line[i] == "'":
                quote = not quote
            elif not quote and line.startswith("--", i):
                cut = i
                break
            i += 1
        if cut is None:
            code_lines.append(line)
        else:
            code_lines.append(line[:cut])
            comments[idx] = line[cut + 2 :].strip()
    return "\n".join(code_lines), comments


def match_close(sql: str, open_at: int) -> int:
    depth, quote, i = 0, False, open_at
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            quote = not quote
        elif not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unbalanced parenthesis")


def split_items(body: str, base: int) -> list[tuple[str, int]]:
    """Top-level comma split of a CREATE TABLE body; returns (text, offset in the full SQL)."""
    items, depth, quote, start = [], 0, False, 0
    for i, ch in enumerate(body):
        if ch == "'":
            quote = not quote
        elif not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                items.append((body[start:i], base + start))
                start = i + 1
    if body[start:].strip():
        items.append((body[start:], base + start))
    # Report the offset of the first non-blank character, so the line numbers point at the item itself.
    result = []
    for text, off in items:
        if text.strip():
            result.append((text.strip(), off + len(text) - len(text.lstrip())))
    return result


def remove_checks(text: str) -> str:
    out, i = "", 0
    while True:
        m = re.search(r"\bCHECK\s*\(", text[i:])
        if not m:
            return out + text[i:]
        start = i + m.start()
        open_at = i + m.end() - 1
        close = match_close(text, open_at)
        out += text[i:start] + " "
        i = close + 1


def parse_column(text: str, note: str) -> dict:
    t = squash(remove_checks(text))
    toks = t.split()
    name = toks[0]
    type_toks = []
    for tok in toks[1:]:
        if tok.upper() in STOP_WORDS:
            break
        type_toks.append(tok)
    up = t.upper()
    default = None
    m = re.search(
        r"\bDEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|REFERENCES|UNIQUE|PRIMARY|GENERATED|CONSTRAINT|COLLATE)\b|$)", t, re.I
    )
    if m:
        default = m.group(1).strip()
    if "GENERATED ALWAYS AS IDENTITY" in up:
        default = "identity"
    elif "GENERATED ALWAYS AS (" in up:
        default = "generated (stored)"
    ref = re.search(r"REFERENCES\s+app\.(\w+)", t)
    return {
        "name": name,
        "type": " ".join(type_toks).replace("app.", ""),
        "nn": bool(re.search(r"\bNOT NULL\b", up)) or "PRIMARY KEY" in up,
        "pk": "PRIMARY KEY" in up,
        "uk": bool(re.search(r"(?<!NULLS )\bUNIQUE\b", up)),
        "default": default,
        "fk": ref.group(1) if ref else None,
        "note": note,
    }


def parse_tables(sql: str, comments: dict[int, str], lines: list[str]) -> list[dict]:
    tables = []
    for m in re.finditer(r"CREATE TABLE app\.(\w+) \(", sql):
        name = m.group(1)
        open_at = m.end() - 1
        close = match_close(sql, open_at)
        line0 = sql[: m.start()].count("\n")
        title_lines = []
        k = line0 - 1
        while k >= 0 and lines[k].strip().startswith("--"):
            title_lines.insert(0, lines[k].strip()[2:].strip())
            k -= 1
        columns, constraints, composite_fk = [], [], {}
        for text, off in split_items(sql[open_at + 1 : close], open_at + 1):
            first = sql[:off].count("\n")
            last = sql[: off + len(text)].count("\n")
            note = " ".join(comments[i] for i in range(first, last + 1) if i in comments)
            if text.upper().startswith(TABLE_CONSTRAINT):
                cname = re.match(r"CONSTRAINT\s+(\w+)", text, re.I)
                fk = re.search(r"FOREIGN KEY \(([^)]*)\)\s*REFERENCES app\.(\w+)", text)
                if fk:
                    for col in fk.group(1).split(","):
                        composite_fk.setdefault(col.strip(), fk.group(2))
                constraints.append({"name": cname.group(1) if cname else "", "text": squash(text)[:170]})
                continue
            columns.append(parse_column(text, note))
        for col in columns:
            if col["name"] == "zone_id" and not col["fk"] and name != "zone":
                col["fk"] = "zone"          # every zone-owned table names its zone (composite FKs cover the parent)
            elif not col["fk"] and col["name"] in composite_fk:
                col["fk"] = composite_fk[col["name"]]
        tables.append(
            {
                "name": name,
                "title": " ".join(title_lines),
                "columns": columns,
                "constraints": constraints,
            }
        )
    return tables


def parse_indexes(sql: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for m in re.finditer(r"CREATE\s+(UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+app\.(\w+)\s*", sql):
        j = m.end()
        using = re.match(r"USING\s+\w+\s*", sql[j:])
        if using:
            j += using.end()
        open_at = sql.index("(", j)
        close = match_close(sql, open_at)
        end = sql.index(";", close)
        rest = squash(sql[close + 1 : end])
        where = rest[len("WHERE ") :] if rest.upper().startswith("WHERE ") else ""
        result.setdefault(m.group(3), []).append(
            {
                "name": m.group(2),
                "unique": bool(m.group(1)),
                "cols": squash(sql[open_at + 1 : close]),
                "where": where,
            }
        )
    return result


def parse_rls(sql: str) -> tuple[set[str], dict[str, list[dict]], dict[str, str]]:
    enabled, policies, grants = set(), {}, {}
    for m in re.finditer(r"ALTER TABLE app\.(\w+) ENABLE ROW LEVEL SECURITY", sql):
        enabled.add(m.group(1))
    for block in re.finditer(r"FOREACH t IN ARRAY ARRAY\[([^\]]*)\] LOOP(.*?)END \$\$;", sql, re.S):
        tables = [t.strip().strip("'") for t in block.group(1).split(",")]
        body = block.group(2)
        pols = [
            {"name": p.group(1), "cmd": p.group(2), "using": "(bảng theo vòng lặp, xem schema.sql §20)"}
            for p in re.finditer(r"CREATE POLICY (\w+) ON app\.%I FOR (\w+)", body)
        ]
        if "ENABLE ROW LEVEL SECURITY" in body:
            enabled.update(tables)
        for t in tables:
            policies.setdefault(t, []).extend(pols)
    for p in re.finditer(r"CREATE POLICY (\w+) ON app\.(\w+) FOR (\w+)(.*?);", sql, re.S):
        policies.setdefault(p.group(2), []).append(
            {
                "name": p.group(1),
                "cmd": p.group(3),
                "using": squash(p.group(4))[:120],
            }
        )
    for g in re.finditer(r"GRANT SELECT \(([^)]*)\)\s+ON app\.(\w+)", sql):
        grants[g.group(2)] = "vai trò app chỉ SELECT được các cột: " + squash(g.group(1))
    for r in re.finditer(r"REVOKE SELECT ON ([^;]*?) FROM parksmart_app", sql):
        for t in r.group(1).split(","):
            name = t.strip().replace("app.", "")
            grants.setdefault(name, "vai trò app không SELECT được (cột nhạy cảm, xem schema.sql §21)")
    return enabled, policies, grants


def build() -> list[dict]:
    raw = SCHEMA.read_text(encoding="utf-8")
    lines = raw.split("\n")
    sql, comments = split_comments(lines)
    tables = parse_tables(sql, comments, lines)
    indexes = parse_indexes(sql)
    enabled, policies, grants = parse_rls(sql)
    group_of = {name: gid for gid, _, names in GROUPS for name in names}
    out = []
    for t in tables:
        name = t["name"]
        for col in t["columns"]:
            key = (name, col["name"])
            col["badge"] = "mới" if key in NEW_COLS else ("đổi" if key in CHANGED_COLS else "")
            col["badge_note"] = CHANGED_COLS.get(key, "")
        pol = policies.get(name, [])
        out.append(
            {
                "name": name,
                "group": group_of.get(name, "??"),
                "new": name in NEW_TABLES,
                "title": t["title"],
                "columns": t["columns"],
                "constraints": t["constraints"],
                "indexes": indexes.get(name, []),
                "rls": {"enabled": name in enabled, "policies": pol},
                "grant": grants.get(name, ""),
                "removed": REMOVED_COLS.get(name, []),
            }
        )
    missing = [n for n in group_of if n not in {t["name"] for t in out}]
    if missing:
        raise SystemExit(f"tables listed in GROUPS but not in schema.sql: {missing}")
    unlisted = [t["name"] for t in out if t["name"] not in group_of]
    if unlisted:
        raise SystemExit(f"tables missing from GROUPS: {unlisted}")
    return out


def main() -> None:
    tables = build()
    groups = [{"id": gid, "label": label} for gid, label, _ in GROUPS]
    data = json.dumps({"groups": groups, "tables": tables}, ensure_ascii=False).replace("</", "<\\/")
    cols = sum(len(t["columns"]) for t in tables)
    html = TEMPLATE.replace("__DATA__", data).replace("__COUNT__", str(len(tables))).replace("__COLS__", str(cols))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(tables)} tables, {cols} columns")


TEMPLATE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Từ điển bảng ParkSmart (v7)</title>
<!-- Generated by scripts/gen_tables_html.py from docs/03-design/sql/schema.sql. Do not edit by hand. -->
<style>
:root { --bg:#f6f7f9; --card:#fff; --ink:#1f2430; --muted:#5b6475; --rule:#dde1e8; --pk:#1f2430; --fk:#2563eb;
        --hl:#fde68a; --new:#15803d; --newbg:#dcfce7; --chg:#b45309; --chgbg:#fef3c7; --chip:#eef1f5;
        --font: system-ui, -apple-system, "Segoe UI", sans-serif; --mono: ui-monospace, SFMono-Regular, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#12151b; --card:#1b1f27; --ink:#e7eaf0;
        --muted:#9aa3b2; --rule:#2c323d; --pk:#e7eaf0; --fk:#7aa7ff; --hl:#5b4a12; --new:#86efac; --newbg:#14532d;
        --chg:#fcd34d; --chgbg:#4a3a10; --chip:#262b35; } }
:root[data-theme="dark"] { --bg:#12151b; --card:#1b1f27; --ink:#e7eaf0; --muted:#9aa3b2; --rule:#2c323d; --pk:#e7eaf0;
        --fk:#7aa7ff; --hl:#5b4a12; --new:#86efac; --newbg:#14532d; --chg:#fcd34d; --chgbg:#4a3a10; --chip:#262b35; }
* { box-sizing: border-box; }
html, body { background:var(--bg); }
body { margin:0; color:var(--ink); font:14px/1.45 var(--font); padding:20px 12px 48px; }
.wrap { max-width:1280px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 12px; }
.bar { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; position:sticky; top:0; background:var(--bg);
       padding:8px 0; z-index:2; }
.bar input, .bar select { font:inherit; padding:6px 10px; border:1px solid var(--rule); border-radius:6px;
                          background:var(--card); color:var(--ink); }
.bar input { min-width:220px; flex:1 1 220px; }
.bar label { color:var(--muted); font-size:13px; display:flex; gap:6px; align-items:center; }
.count { color:var(--muted); font-size:12px; }
.legend { color:var(--muted); font-size:12px; margin:4px 0 12px; }
.legend b { font-family:var(--mono); font-weight:600; }
section { margin:18px 0 6px; }
section h2 { font-size:13px; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); margin:0 0 8px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 340px), 1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--rule); border-radius:8px; overflow:hidden; min-width:0; }
.card h3 { margin:0; padding:8px 12px; font:600 14px var(--mono); border-bottom:1px solid var(--rule); display:flex;
           justify-content:space-between; gap:8px; flex-wrap:wrap; }
.card h3 small { font:400 11px var(--font); color:var(--muted); align-self:center; }
.desc { margin:0; padding:6px 12px; color:var(--muted); font-size:12px; border-bottom:1px solid var(--rule); }
.wrapx { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th { text-align:left; font-weight:600; color:var(--muted); padding:4px 8px; border-bottom:1px solid var(--rule); white-space:nowrap; }
td { padding:4px 8px; border-top:1px solid var(--rule); vertical-align:top; }
td.n { font-family:var(--mono); word-break:break-word; }
td.t { font-family:var(--mono); color:var(--muted); word-break:break-word; }
td.d { font-family:var(--mono); color:var(--muted); word-break:break-word; }
td.note { color:var(--ink); }
tr.newrow td { background:var(--newbg); }
tr.chgrow td { background:var(--chgbg); }
tr.match td { background:var(--hl); }
.k { display:inline-block; font:600 9px var(--mono); padding:0 4px; border-radius:3px; background:var(--chip); margin-left:4px; }
.k.pk { background:var(--pk); color:var(--card); }
.k.fk { color:var(--fk); }
.badge { display:inline-block; font:600 10px var(--font); padding:0 5px; border-radius:4px; margin-left:4px; }
.badge.new { background:var(--newbg); color:var(--new); }
.badge.chg { background:var(--chgbg); color:var(--chg); }
details { padding:4px 12px 8px; border-top:1px solid var(--rule); font-size:12px; }
summary { cursor:pointer; color:var(--muted); padding:4px 0; }
details ul { margin:4px 0 0; padding-left:18px; }
details li { margin:2px 0; font-family:var(--mono); word-break:break-word; }
.meta { padding:6px 12px; font-size:12px; color:var(--muted); border-top:1px solid var(--rule); }
@media (max-width:480px) {
  body { padding:12px 8px 32px; }
  .bar input { min-width:0; width:100%; }
  td, th { padding:3px 5px; }
}
</style>
</head>
<body>
<div class="wrap">
  <h1>Từ điển bảng ParkSmart (v7, __COUNT__ bảng, __COLS__ cột)</h1>
  <p class="sub">Sinh tự động từ <code>docs/03-design/sql/schema.sql</code> bằng <code>python scripts/gen_tables_html.py</code>.
     Ghi chú cột là comment SQL cạnh cột. Chi tiết nghiệp vụ: <a href="../03-data-dictionary.md">03-data-dictionary.md</a>.</p>
  <div class="bar">
    <input id="q" type="search" placeholder="Tìm bảng, cột hoặc ghi chú…" aria-label="Tìm bảng, cột hoặc ghi chú">
    <select id="g" aria-label="Lọc theo nhóm"></select>
    <label><input id="onlyNew" type="checkbox"> chỉ cột mới / đổi (plan 024)</label>
    <span class="count" id="count"></span>
  </div>
  <p class="legend"><b>PK</b> khóa chính · <b>FK</b> khóa ngoại (→ bảng) · <b>NN</b> bắt buộc · <b>UK</b> duy nhất ·
     <span class="badge new">mới</span> thêm ở plan 024 · <span class="badge chg">đổi</span> đổi giá trị hoặc tên</p>
  <div id="root"></div>
</div>
<script>
const DATA = __DATA__;
const root = document.getElementById('root');
const gSel = document.getElementById('g');
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
gSel.innerHTML = '<option value="">Tất cả nhóm</option>' +
  DATA.groups.map(g => '<option value="' + esc(g.id) + '">' + esc(g.id + ' · ' + g.label) + '</option>').join('');
const cards = [];
DATA.groups.forEach(g => {
  const tables = DATA.tables.filter(t => t.group === g.id);
  if (!tables.length) return;
  const sec = document.createElement('section');
  sec.dataset.group = g.id;
  sec.innerHTML = '<h2>' + esc(g.id + ' · ' + g.label) + '</h2><div class="grid"></div>';
  const grid = sec.querySelector('.grid');
  tables.forEach(t => {
    const card = document.createElement('article');
    card.className = 'card';
    card.dataset.name = t.name;
    const rows = t.columns.map(c => {
      const cls = c.badge === 'mới' ? 'newrow' : (c.badge === 'đổi' ? 'chgrow' : '');
      const flags = (c.pk ? '<span class="k pk">PK</span>' : '') + (c.fk ? '<span class="k fk">FK</span>' : '')
        + (c.uk && !c.pk ? '<span class="k">UK</span>' : '') + (c.nn && !c.pk ? '<span class="k">NN</span>' : '')
        + (c.badge === 'mới' ? '<span class="badge new">mới</span>' : '')
        + (c.badge === 'đổi' ? '<span class="badge chg">đổi</span>' : '');
      const note = [c.note, c.badge_note].filter(Boolean).join(' — ');
      return '<tr class="' + cls + '" data-col="' + esc(c.name) + '" data-new="' + (c.badge ? '1' : '0') + '">'
        + '<td class="n">' + esc(c.name) + flags + '</td>'
        + '<td class="t">' + esc(c.type) + '</td>'
        + '<td>' + (c.nn ? 'không' : 'có') + '</td>'
        + '<td class="d">' + esc(c.default || '') + '</td>'
        + '<td class="n">' + (c.fk ? '→ ' + esc(c.fk) : '') + '</td>'
        + '<td class="note">' + esc(note) + '</td></tr>';
    }).join('');
    const cons = t.constraints.length
      ? '<details><summary>Ràng buộc bảng (' + t.constraints.length + ')</summary><ul>'
        + t.constraints.map(c => '<li>' + (c.name ? esc(c.name) + ': ' : '') + esc(c.text) + '</li>').join('') + '</ul></details>' : '';
    const idx = t.indexes.length
      ? '<details><summary>Index (' + t.indexes.length + ')</summary><ul>'
        + t.indexes.map(i => '<li>' + (i.unique ? 'UNIQUE ' : '') + esc(i.name) + ' (' + esc(i.cols) + ')'
          + (i.where ? ' WHERE ' + esc(i.where) : '') + '</li>').join('') + '</ul></details>' : '';
    const pols = t.rls.policies.map(p => esc(p.name) + ' [' + esc(p.cmd) + ']').join(' · ');
    const rls = t.rls.enabled
      ? 'RLS bật' + (pols ? ': ' + pols : '') : 'Không bật RLS (dữ liệu cấu hình, xem schema.sql §20)';
    const removed = t.removed.length ? '<div class="meta">Đã bỏ: ' + esc(t.removed.join('; ')) + '</div>' : '';
    const grant = t.grant ? '<div class="meta">Quyền cột: ' + esc(t.grant) + '</div>' : '';
    const newBadge = t.new ? '<span class="badge new">bảng mới</span>' : '';
    card.innerHTML = '<h3><span>' + esc(t.name) + newBadge + '</span><small>' + t.columns.length + ' cột · '
      + t.indexes.length + ' index</small></h3>'
      + (t.title ? '<p class="desc">' + esc(t.title) + '</p>' : '')
      + '<div class="wrapx"><table><thead><tr><th>Cột</th><th>Kiểu</th><th>Null</th><th>Mặc định</th><th>FK</th><th>Ghi chú</th></tr></thead><tbody>'
      + rows + '</tbody></table></div>'
      + removed + cons + idx + '<div class="meta">' + esc(rls) + '</div>' + grant;
    grid.appendChild(card);
    cards.push({card, sec, t, group: g.id});
  });
  root.appendChild(sec);
});
function apply() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const grp = gSel.value;
  const onlyNew = document.getElementById('onlyNew').checked;
  let shown = 0;
  cards.forEach(({card, t, group}) => {
    let hit = (!grp || group === grp);
    if (hit && q) {
      const text = [t.name, t.title, ...t.columns.map(c => c.name + ' ' + c.note + ' ' + c.type)].join(' ').toLowerCase();
      hit = text.includes(q);
    }
    if (hit && onlyNew) hit = t.new || t.columns.some(c => c.badge);
    card.querySelectorAll('tbody tr').forEach(tr => {
      const colHit = q && tr.dataset.col.toLowerCase().includes(q);
      tr.classList.toggle('match', !!colHit);
      tr.style.display = (onlyNew && tr.dataset.new !== '1') ? 'none' : '';
    });
    card.style.display = hit ? '' : 'none';
    if (hit) shown++;
  });
  document.querySelectorAll('section').forEach(s => {
    s.style.display = [...s.querySelectorAll('.card')].some(c => c.style.display !== 'none') ? '' : 'none';
  });
  document.getElementById('count').textContent = shown + ' / ' + cards.length + ' bảng';
}
document.getElementById('q').addEventListener('input', apply);
gSel.addEventListener('change', apply);
document.getElementById('onlyNew').addEventListener('change', apply);
apply();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
