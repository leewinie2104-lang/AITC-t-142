#!/usr/bin/env python3
"""Generate docs/03-design/diagrams/schema-diagram.html from docs/03-design/sql/schema.sql.

Run from the repo root after any schema change:
    python scripts/gen_schema_diagram.py

Stdlib only, deterministic. Reads every `CREATE TABLE app.<name> (...)` block: columns (type, NOT NULL, PK, UNIQUE, FK,
DEFAULT, SQL comment), table-level FOREIGN KEY clauses, indexes and RLS policies. Draws all tables on one SVG canvas,
clustered in tinted regions by the groups of docs/03-design/dictionary/01…09, with one line per foreign-key column.
Clicking a table highlights its links and opens its data dictionary (columns, defaults, notes, indexes, RLS).
Columns and tables whose comment names the current schema version (e.g. "v7") get a version chip.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "docs" / "03-design" / "sql" / "schema.sql"
OUT = ROOT / "docs" / "03-design" / "diagrams" / "schema-diagram.html"

# Same groups and order as docs/03-design/dictionary/01…09. (id, label, modules, tint, ink, tables)
GROUPS = [
    ("fac", "Cơ sở vật chất & pool", "M2 · M3", "#e8eef7", "#3b5b8c", ["zone", "building", "slot_pool", "slot"]),
    ("idn", "Tài khoản & nội quy", "M1 · M3", "#e9f3ee", "#2f6b4f", ["app_user", "vehicle", "zone_policy"]),
    (
        "elg",
        "Tư cách & đăng ký BQL",
        "M1 · BR-26",
        "#eaf4f4",
        "#2d6e70",
        ["asset", "eligibility", "slot_holding", "bql_registry_import"],
    ),
    ("shr", "Chia sẻ & yêu cầu", "M4 · M5", "#fdf0e8", "#b4541f", ["share_window", "parking_request"]),
    ("bkg", "Đặt chỗ & chủ về sớm", "M5 · M9", "#f6efe6", "#8f4a1c", ["booking", "recovery_case"]),
    ("agr", "Thỏa thuận & thanh toán", "M6 · M7", "#fbeeee", "#9a3b3b", ["agreement", "consent_record", "payment"]),
    ("ops", "Vận hành", "M8 · M12 · M13", "#eef0f2", "#4f5d75", ["lpr_event", "approval_request", "notification"]),
    (
        "agt",
        "Agent & tri thức",
        "M14 · W7",
        "#f3ecf7",
        "#6b4a8a",
        ["agent_thread", "ai_decision_log", "knowledge_chunk"],
    ),
    ("dsp", "Tranh chấp", "M10 · W5", "#f6f1e4", "#8a6a1f", ["dispute_case", "dispute_evidence"]),
]
HUBS = {"zone", "app_user"}

# Layout (px). Three region columns, two table columns per region.
TW, PAD, GAP, REGION_GAP_X, REGION_GAP_Y, HEAD, ROW = 236, 18, 18, 90, 36, 40, 16
REGION_W = PAD * 3 + TW * 2
COLS_X = [30 + i * (REGION_W + REGION_GAP_X) for i in range(3)]

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


# ---------------------------------------------------------------- parsing


def comment_at(line: str) -> int:
    """Index of the `--` that starts a comment in this line, ignoring `--` inside single quotes; -1 if none."""
    quote = False
    for i, ch in enumerate(line):
        if ch == "'":
            quote = not quote
        elif not quote and line.startswith("--", i):
            return i
    return -1


def code_of(line: str) -> str:
    cut = comment_at(line)
    return line if cut < 0 else line[:cut]


def note_of(line: str) -> str:
    cut = comment_at(line)
    return "" if cut < 0 else line[cut + 2 :].strip()


def squash(text: str) -> str:
    return " ".join(text.split())


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


def column_default(item: str) -> str | None:
    if re.search(r"GENERATED ALWAYS AS IDENTITY", item, re.I):
        return "identity"
    if re.search(r"GENERATED ALWAYS AS \(", item, re.I):
        return "generated (stored)"
    m = re.search(
        r"\bDEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|REFERENCES|UNIQUE|PRIMARY|CHECK|GENERATED|CONSTRAINT|COLLATE)\b|$)",
        squash(item),
        re.I,
    )
    return m.group(1).strip() if m else None


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
        "uk": bool(re.search(r"(?<!NULLS )\bUNIQUE\b", upper)),
        "fk": ref.group(1) if ref else None,
        "default": column_default(item),
    }


def column_notes(lines: list[str], first: int) -> dict[str, tuple[str, str]]:
    """Column name -> (own comment, comment block right above it)."""
    notes: dict[str, tuple[str, str]] = {}
    depth, block, pending, i = 0, "", [], first
    while i < len(lines):
        code = code_of(lines[i]).strip()
        if i > first and depth == 1:
            if not code and note_of(lines[i]):
                pending.append(note_of(lines[i]))
            elif not code:
                block, pending = "", []
            else:
                block, pending = " ".join(pending), []
                if not code.upper().startswith(TABLE_CONSTRAINT) and not code.startswith(")"):
                    notes.setdefault(code.split()[0].rstrip(","), (note_of(lines[i]), block))
                block = ""  # a comment block above describes the next column only
        depth += code.count("(") - code.count(")")
        if i > first and depth <= 0:
            break
        i += 1
    return notes


def table_title(lines: list[str], first: int) -> str:
    out, k = [], first - 1
    while k >= 0 and lines[k].strip().startswith("--") and not re.match(r"^-- \d+[a-z.]*\d* ", lines[k].strip()):
        text = lines[k].strip()[2:].strip()
        if text and not set(text) <= {"-", "="}:
            out.insert(0, text)
        k -= 1
    return " ".join(out)


def parse_indexes(sql: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    pattern = r"CREATE\s+(UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+app\.(\w+)\s*(?:USING\s+\w+\s*)?\("
    for m in re.finditer(pattern, sql):
        close = match_close(sql, m.end() - 1)
        rest = squash(sql[close + 1 : sql.index(";", close)])
        result.setdefault(m.group(3), []).append(
            {
                "name": m.group(2),
                "unique": bool(m.group(1)),
                "cols": squash(sql[m.end() : close]),
                "where": rest[6:] if rest.upper().startswith("WHERE ") else "",
            }
        )
    return result


def parse_rls(sql: str) -> dict[str, dict]:
    rls: dict[str, dict] = {}

    def entry(name: str) -> dict:
        return rls.setdefault(name, {"on": False, "policies": []})

    for m in re.finditer(r"ALTER TABLE app\.(\w+) ENABLE ROW LEVEL SECURITY", sql):
        entry(m.group(1))["on"] = True
    for block in re.finditer(r"FOREACH t IN ARRAY ARRAY\[([^\]]*)\] LOOP(.*?)END \$\$;", sql, re.S):
        body = block.group(2)
        pols = [f"{p.group(1)} ({p.group(2)})" for p in re.finditer(r"CREATE POLICY (\w+) ON app\.%I FOR (\w+)", body)]
        for t in (x.strip().strip("'") for x in block.group(1).split(",")):
            e = entry(t)
            e["on"] = e["on"] or "ENABLE ROW LEVEL SECURITY" in body
            e["policies"].extend(pols)
    for p in re.finditer(r"CREATE POLICY (\w+) ON app\.(\w+) FOR (\w+)", sql):
        entry(p.group(2))["policies"].append(f"{p.group(1)} ({p.group(3)})")
    return rls


def parse(raw: str, version: str) -> list[dict]:
    lines = raw.split("\n")
    sql = "\n".join(code_of(line) for line in lines)  # same offsets per line, comments blanked
    indexes, rls = parse_indexes(sql), parse_rls(sql)
    ver_re = re.compile(rf"\b{re.escape(version)}\b")
    tables = []
    for m in TABLE_RE.finditer(sql):
        name, first = m.group(1), sql[: m.start()].count("\n")
        body = sql[m.end() : match_close(sql, m.end() - 1)]
        columns, fks = [], []
        for item in split_top_level(body):
            if not item:
                continue
            if item.upper().startswith(TABLE_CONSTRAINT):
                fk = re.search(r"FOREIGN KEY \(([^)]*)\)\s+REFERENCES app\.(\w+)", item)
                if fk:
                    for pos, col in enumerate(c.strip() for c in fk.group(1).split(",")):
                        fks.append((col, fk.group(2), pos))
                continue
            columns.append(parse_column(item))
        notes = column_notes(lines, first)
        for col in columns:
            # A column in several composite FKs points at the FK where it comes first (booking.slot_id -> slot).
            candidates = sorted((pos, i, target) for i, (c, target, pos) in enumerate(fks) if c == col["name"])
            if candidates and col["name"] != "zone_id" and not col["fk"]:
                col["fk"] = candidates[0][2]
            if col["name"] == "zone_id" and not col["fk"] and name != "zone":
                col["fk"] = "zone"
            own, block = notes.get(col["name"], ("", ""))
            col["note"] = own or block
            col["ver"] = bool(ver_re.search(own) or ver_re.search(block))
        title = table_title(lines, first)
        tables.append(
            {
                "name": name,
                "title": title,
                "ver": bool(ver_re.search(title)),
                "columns": columns,
                "indexes": indexes.get(name, []),
                "rls": rls.get(name, {"on": False, "policies": []}),
            }
        )
    return tables


# ---------------------------------------------------------------- layout and SVG


def table_height(t: dict) -> int:
    return 26 + ROW * len(t["columns"]) + 6


def layout(tables: dict[str, dict]) -> tuple[list[dict], int]:
    """Place regions in the shortest of three columns, tables in the shorter of two sub-columns."""
    col_y = [30, 30, 30]
    regions = []
    for gid, label, mods, tint, ink, names in GROUPS:
        sub = [0, 0]
        for n in names:
            k = 0 if sub[0] <= sub[1] else 1
            tables[n]["_sub"], tables[n]["_dy"] = k, sub[k]
            sub[k] += table_height(tables[n]) + GAP
        height = HEAD + max(sub) + PAD - GAP + 2
        c = min(range(3), key=lambda i: (col_y[i], i))
        x, y = COLS_X[c], col_y[c]
        for n in names:
            t = tables[n]
            t["x"], t["y"], t["group"], t["ink"] = x + PAD + t["_sub"] * (TW + PAD), y + HEAD + t["_dy"], gid, ink
        regions.append({"id": gid, "label": label, "mods": mods, "tint": tint, "ink": ink, "x": x, "y": y, "h": height})
        col_y[c] += height + REGION_GAP_Y
    return regions, max(col_y)


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def fit(name: str, typ: str, chips: int) -> str:
    room = TW - 20 - chips * 21 - len(name) * 6.3
    max_chars = max(4, int(room / 6.1))
    return typ if len(typ) <= max_chars else typ[: max_chars - 1] + "…"


def edge_path(s: dict, row: int, t: dict) -> str:
    sy = s["y"] + 34 + ROW * row
    ty = t["y"] + 13
    scx, tcx = s["x"] + TW / 2, t["x"] + TW / 2
    if s is t or abs(scx - tcx) < 10:
        sx, tx = s["x"] + TW, t["x"] + TW
        bulge = 40 + min(60, abs(sy - ty) * 0.08)
        return f"M{sx},{sy} C{sx + bulge:.1f},{sy} {tx + bulge:.1f},{ty} {tx},{ty}"
    if tcx > scx:
        sx, tx = s["x"] + TW, t["x"]
    else:
        sx, tx = s["x"], t["x"] + TW
    dx = (tx - sx) * 0.45
    return f"M{sx},{sy} C{sx + dx:.1f},{sy} {tx - dx:.1f},{ty} {tx},{ty}"


def svg_table(t: dict, version: str) -> str:
    x, y, h, ink = t["x"], t["y"], table_height(t), t["ink"]
    changed = t["ver"] or any(c["ver"] for c in t["columns"])
    out = [
        f'<g class="tbl" data-t="{t["name"]}" data-ver="{1 if changed else 0}" tabindex="0">',
        f'<rect x="{x}" y="{y}" width="{TW}" height="{h}" rx="5" class="tbox"/>',
        f'<rect x="{x}" y="{y}" width="{TW}" height="26" rx="5" fill="{ink}"/>',
        f'<rect x="{x}" y="{y + 20}" width="{TW}" height="6" fill="{ink}"/>',
        f'<text x="{x + 10}" y="{y + 17}" class="tname">{esc(t["name"])}</text>',
    ]
    if changed:
        out.append(f'<text x="{x + TW - 10}" y="{y + 17}" class="ttag" text-anchor="end">{esc(version.upper())}</text>')
    for i, c in enumerate(t["columns"]):
        ry = y + 26 + ROW * i
        chips = [k for k, on in (("PK", c["pk"]), ("FK", c["fk"]), ("UQ", c["uk"]), (version, c["ver"])) if on]
        tip = f"{c['name']} {c['type']}" + (" · NOT NULL" if c["nn"] else "")
        tip += (f" · DEFAULT {c['default']}" if c["default"] else "") + (f" · → {c['fk']}" if c["fk"] else "")
        tip += f" — {c['note']}" if c["note"] else ""
        out.append(f'<g class="crow"><title>{esc(tip)}</title>')
        if i % 2:
            out.append(f'<rect x="{x + 1}" y="{ry}" width="{TW - 2}" height="{ROW}" class="zebra"/>')
        cx = x + 10
        for k in chips:
            cls = {"PK": "pk", "FK": "fk", "UQ": "uq"}.get(k, "ver")
            out.append(f'<rect x="{cx}" y="{ry + 3}" width="18" height="10" rx="2" class="chip {cls}"/>')
            out.append(f'<text x="{cx + 9}" y="{ry + 11}" class="chipt" text-anchor="middle">{esc(k)}</text>')
            cx += 21
        label = c["name"] + ("" if c["nn"] else "?")
        key = " key" if (c["pk"] or c["fk"] or c["uk"]) else ""
        out.append(f'<text x="{cx + (3 if chips else 0)}" y="{ry + 12}" class="col{key}">{esc(label)}</text>')
        typ = fit(label, c["type"], len(chips))
        out.append(f'<text x="{x + TW - 10}" y="{ry + 12}" class="ctype" text-anchor="end">{esc(typ)}</text></g>')
    out.append("</g>")
    return "".join(out)


def render(tables: list[dict], version: str) -> str:
    by_name = {t["name"]: t for t in tables}
    grouped = [n for g in GROUPS for n in g[5]]
    missing = sorted(set(by_name) - set(grouped))
    extra = sorted(set(grouped) - set(by_name))
    if missing or extra:
        raise SystemExit(f"GROUPS out of sync with schema.sql: missing {missing}, unknown {extra}")
    regions, height = layout(by_name)
    width = COLS_X[-1] + REGION_W + 30
    parts = [
        f'<svg id="canvas" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{len(tables)} bảng của schema ParkSmart {version}, gom theo module">',
        '<defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/></marker></defs>',
    ]
    for r in regions:
        parts.append(
            f'<g class="region" data-group="{r["id"]}"><rect x="{r["x"]}" y="{r["y"]}" width="{REGION_W}" '
            f'height="{r["h"]}" rx="10" fill="{r["tint"]}" stroke="{r["ink"]}" stroke-opacity=".25"/>'
            f'<text x="{r["x"] + 18}" y="{r["y"] + 24}" class="rlabel" fill="{r["ink"]}">{esc(r["label"].upper())}</text>'
            f'<text x="{r["x"] + REGION_W - 18}" y="{r["y"] + 24}" class="rsub" text-anchor="end" '
            f'fill="{r["ink"]}">{esc(r["mods"])}</text></g>'
        )
    edges = []
    for t in tables:
        for i, c in enumerate(t["columns"]):
            if c["fk"] and c["fk"] in by_name:
                hub = " hub" if c["fk"] in HUBS and c["fk"] != t["name"] else ""
                edges.append(
                    f'<path class="edge{hub}" data-s="{t["name"]}" data-t="{c["fk"]}" '
                    f'd="{edge_path(t, i, by_name[c["fk"]])}" stroke="{t["ink"]}" marker-end="url(#arr)">'
                    f"<title>{esc(t['name'])}.{esc(c['name'])} → {esc(c['fk'])}</title></path>"
                )
    parts.append('<g id="edges" fill="none">' + "".join(edges) + "</g>")
    parts.extend(svg_table(by_name[n], version) for n in grouped)
    parts.append("</svg>")
    legend = "".join(
        f'<li><i style="background:{tint};border-color:{ink}"></i><b style="color:{ink}">{esc(label)}</b> '
        f"<span>{esc(', '.join(names))}</span></li>"
        for _, label, _, tint, ink, names in GROUPS
    )
    detail = {
        t["name"]: {k: t[k] for k in ("title", "ver", "columns", "indexes", "rls")} | {"group": t["group"]}
        for t in tables
    }
    cols = sum(len(t["columns"]) for t in tables)
    ver_cols = sum(c["ver"] for t in tables for c in t["columns"])
    return (
        TEMPLATE.replace("__SVG__", "".join(parts))
        .replace("__LEGEND__", legend)
        .replace("__DATA__", json.dumps(detail, ensure_ascii=False).replace("</", "<\\/"))
        .replace("__VERSION__", version)
        .replace("__COUNT__", str(len(tables)))
        .replace("__COLS__", str(cols))
        .replace("__EDGES__", str(len(edges)))
        .replace("__VERCOLS__", str(ver_cols))
    )


def main() -> None:
    raw = SCHEMA.read_text(encoding="utf-8")
    version = (re.search(r"^-- (v\d+) \(", raw, re.MULTILINE) or re.search(r"(v\d+)", raw)).group(1)
    tables = parse(raw, version)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(tables, version), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(tables)} tables ({version})")


TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sơ đồ schema ParkSmart</title>
<!-- Generated by scripts/gen_schema_diagram.py from docs/03-design/sql/schema.sql. Do not edit by hand. -->
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root { --paper: #f5f5f5; --card: #ffffff; --ink: #2d3142; --muted: #4f5d75; --rule: rgba(45,49,66,0.12);
          --ver: #b45309; --verbg: #fdecd3;
          --sans: 'Geist', system-ui, sans-serif; --serif: 'Instrument Serif', serif; --mono: 'Geist Mono', ui-monospace, monospace; }
  body { font-family: var(--sans); background: var(--paper); color: var(--ink); padding: 2rem 1rem 3rem; }
  .frame { max-width: 1480px; margin: 0 auto; }
  .eyebrow { font-family: var(--mono); font-size: .66rem; letter-spacing: .18em; text-transform: uppercase; color: var(--muted); margin-bottom: .5rem; }
  h1 { font-family: var(--serif); font-weight: 400; font-size: clamp(1.6rem, 2.4vw + .75rem, 2.2rem); letter-spacing: -.02em; line-height: 1.15; margin-bottom: .5rem; }
  .sub { color: var(--muted); font-size: .9rem; max-width: 86ch; margin-bottom: 1rem; }
  .sub a, footer a { color: var(--ink); }
  .groups { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: .35rem 1.5rem;
            padding: .9rem 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); font-size: .8rem; }
  .groups i { display: inline-block; width: 12px; height: 12px; border: 1px solid; border-radius: 3px; vertical-align: -1px; margin-right: .4rem; }
  .groups span { display: block; font-family: var(--mono); font-size: .66rem; color: var(--muted); margin-left: 1.3rem; }
  .bar { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; align-items: center; padding: .75rem 0; font-size: .78rem; color: var(--muted); }
  .bar button { font: 500 .75rem var(--sans); border: 1px solid var(--rule); background: var(--card); color: var(--ink);
                 padding: .3rem .7rem; border-radius: 4px; cursor: pointer; }
  .bar button[aria-pressed="true"] { background: var(--ink); color: #fff; }
  .bar input { font: .78rem var(--sans); border: 1px solid var(--rule); background: var(--card); color: var(--ink);
               padding: .3rem .6rem; border-radius: 4px; min-width: 200px; }
  .bar code { font-family: var(--mono); font-size: .72rem; }
  .stage { overflow: auto; border: 1px solid var(--rule); border-radius: 8px; background: #fbfbfa; max-height: 85vh; }
  .stage.fit svg { width: 100%; height: auto; }
  svg { display: block; }
  .rlabel { font: 600 12px var(--mono); letter-spacing: .14em; }
  .rsub { font: 500 10.5px var(--mono); opacity: .8; }
  .tbox { fill: var(--card); stroke: var(--ink); stroke-width: 1; }
  .zebra { fill: rgba(45,49,66,0.035); }
  .tname { font: 600 12.5px var(--sans); fill: #fff; }
  .ttag { font: 600 9px var(--mono); letter-spacing: .1em; fill: #fff; opacity: .9; }
  .col { font: 400 11px var(--sans); fill: var(--ink); }
  .col.key { font-weight: 600; }
  .ctype { font: 400 10px var(--mono); fill: var(--muted); }
  .chip { fill: #fff; stroke: rgba(45,49,66,.45); stroke-width: .8; }
  .chip.pk { fill: #2d3142; stroke: #2d3142; }
  .chip.fk { fill: #fde3d5; stroke: #eb6c36; }
  .chip.uq { fill: #e4ecf6; stroke: #3b5b8c; }
  .chip.ver { fill: var(--verbg); stroke: var(--ver); }
  .chipt { font: 600 7px var(--mono); fill: var(--ink); }
  .chip.pk + .chipt { fill: #fff; }
  .edge { stroke-width: 1.3; stroke-opacity: .5; transition: stroke-opacity .15s, stroke-width .15s; }
  .edge.hub { stroke-opacity: .2; stroke-dasharray: 4 3; }
  .tbl { cursor: pointer; transition: opacity .15s; }
  .tbl:focus { outline: none; }
  .tbl.hit .tbox { stroke: var(--ver); stroke-width: 2.5; }
  svg.focus .edge { stroke-opacity: .05; }
  svg.focus .tbl { opacity: .3; }
  svg.focus .edge.on { stroke-opacity: 1; stroke-width: 2.2; stroke-dasharray: none; }
  svg.focus .tbl.on { opacity: 1; }
  svg.hide-hub .edge.hub { display: none; }
  svg.only-ver .tbl[data-ver="0"] { opacity: .25; }
  #detail { margin-top: 1rem; background: var(--card); border: 1px solid var(--rule); border-radius: 8px; padding: 1rem 1.25rem; }
  #detail[hidden] { display: none; }
  #detail h2 { font: 600 1rem var(--mono); display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; margin-bottom: .35rem; }
  #detail h2 button { margin-left: auto; font: 500 .72rem var(--sans); border: 1px solid var(--rule); background: var(--paper);
                      color: var(--ink); padding: .25rem .6rem; border-radius: 4px; cursor: pointer; }
  #detail p { color: var(--muted); font-size: .82rem; margin-bottom: .6rem; max-width: 110ch; }
  #detail h3 { font: 600 .66rem var(--mono); letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 1rem 0 .4rem; }
  .scroll { overflow-x: auto; }
  #detail table { border-collapse: collapse; width: 100%; min-width: 720px; font-size: .78rem; }
  #detail th { text-align: left; font: 600 .66rem var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
               padding: .35rem .5rem; border-bottom: 1px solid var(--rule); }
  #detail td { padding: .3rem .5rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
  #detail td.m { font-family: var(--mono); font-size: .74rem; word-break: break-word; }
  #detail td.n { color: var(--muted); min-width: 260px; }
  #detail tr.ver td { background: var(--verbg); }
  #detail ul { list-style: none; font-family: var(--mono); font-size: .72rem; line-height: 1.7; }
  .tag { display: inline-block; font: 600 .6rem var(--mono); padding: .05rem .35rem; border-radius: 3px; border: 1px solid var(--ver);
         background: var(--verbg); color: var(--ver); letter-spacing: .08em; }
  footer { margin-top: 1.25rem; padding-top: .75rem; border-top: 1px solid var(--rule); font-family: var(--mono);
            font-size: .68rem; color: var(--muted); line-height: 1.6; }
  @media (max-width: 480px) { .bar input { min-width: 0; width: 100%; } }
</style>
</head>
<body>
<div class="frame">
  <p class="eyebrow">ParkSmart AI · database __VERSION__ (MVP) · one canvas</p>
  <h1>Toàn bộ __COUNT__ bảng trên một sơ đồ, gom theo module</h1>
  <p class="sub">Mọi bảng của <code>schema.sql</code> __VERSION__ (__COLS__ cột). Bảng cùng nhóm nằm chung một vùng màu, giống
    <a href="../dictionary/">dictionary/01…09</a>; mỗi đường là một khóa ngoại (cột nguồn → bảng đích).
    Bấm một bảng để tô sáng liên kết và mở từ điển cột bên dưới; rê chuột lên một cột để xem kiểu, mặc định và ghi chú.
    Chip <span class="tag">__VERSION__</span> đánh dấu __VERCOLS__ cột có ghi chú thay đổi ở __VERSION__.
    Tổng quan: <a href="../01-data-model.md">01-data-model.md</a> · bảng hoãn: <a href="../08-deferred-tables.md">08-deferred-tables.md</a>.</p>
  <ul class="groups">__LEGEND__</ul>
  <div class="bar">
    <button type="button" id="fit" aria-pressed="true">Vừa chiều ngang</button>
    <button type="button" id="hub" aria-pressed="false">Ẩn đường tới zone / app_user</button>
    <button type="button" id="ver" aria-pressed="false">Chỉ bảng có thay đổi __VERSION__</button>
    <input id="q" type="search" placeholder="Tìm bảng hoặc cột…" aria-label="Tìm bảng hoặc cột">
    <span>Bấm hoặc focus một bảng để xem liên kết · <code>?</code> = cho phép NULL · nét đứt = FK tới bảng trung tâm</span>
  </div>
  <div class="stage fit" id="stage">__SVG__</div>
  <section id="detail" hidden></section>
  <footer>Sinh từ <code>docs/03-design/sql/schema.sql</code> bằng <code>python scripts/gen_schema_diagram.py</code>
    (__COUNT__ bảng, __EDGES__ đường khóa ngoại; khóa ghép vẽ từ từng cột). RLS = row-level security.
    Đổi schema thì chạy lại script, không sửa tay file này. View <code>kpi_daily_v</code> và hàm không vẽ ở đây.</footer>
</div>
<script>
(function () {
  var DATA = __DATA__, VERSION = '__VERSION__';
  var svg = document.getElementById('canvas'), stage = document.getElementById('stage'), detail = document.getElementById('detail');
  var edges = svg.querySelectorAll('.edge'), tbls = svg.querySelectorAll('.tbl'), current = null;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function clear() {
    svg.classList.remove('focus'); svg.querySelectorAll('.on').forEach(function (n) { n.classList.remove('on'); });
    current = null; detail.hidden = true;
  }
  function show(name) {
    var t = DATA[name], tag = '<span class="tag">' + VERSION + '</span>';
    var rows = t.columns.map(function (c) {
      return '<tr' + (c.ver ? ' class="ver"' : '') + '><td class="m">' + esc(c.name) + (c.pk ? ' · PK' : '') + (c.ver ? ' ' + tag : '')
        + '</td><td class="m">' + esc(c.type) + '</td><td>' + (c.nn ? 'có' : '') + '</td><td class="m">' + esc(c.default || '')
        + '</td><td class="m">' + (c.fk ? '→ ' + esc(c.fk) : '') + (c.uk ? ' UQ' : '') + '</td><td class="n">' + esc(c.note || '') + '</td></tr>';
    }).join('');
    var idx = t.indexes.map(function (i) {
      return '<li>' + (i.unique ? 'UNIQUE ' : '') + esc(i.name) + ' (' + esc(i.cols) + ')' + (i.where ? ' WHERE ' + esc(i.where) : '') + '</li>';
    }).join('');
    var pol = t.rls.policies.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('');
    detail.innerHTML = '<h2>' + esc(name) + (t.ver ? ' ' + tag : '') + '<button type="button" id="close">Đóng</button></h2>'
      + (t.title ? '<p>' + esc(t.title) + '</p>' : '')
      + '<div class="scroll"><table><thead><tr><th>Cột</th><th>Kiểu</th><th>Bắt buộc</th><th>Mặc định</th><th>Khóa</th><th>Ghi chú</th></tr></thead><tbody>'
      + rows + '</tbody></table></div>'
      + '<h3>Index</h3>' + (idx ? '<ul>' + idx + '</ul>' : '<p>Không có index riêng.</p>')
      + '<h3>RLS</h3><p>' + (t.rls.on ? 'Bật' : 'Không bật') + '</p>' + (pol ? '<ul>' + pol + '</ul>' : '');
    detail.hidden = false;
    document.getElementById('close').addEventListener('click', clear);
  }
  function focus(name) {
    if (current === name) { clear(); return; }
    clear(); current = name; svg.classList.add('focus');
    var keep = {}; keep[name] = 1;
    edges.forEach(function (p) {
      if (p.dataset.s === name || p.dataset.t === name) { p.classList.add('on'); keep[p.dataset.s] = 1; keep[p.dataset.t] = 1; }
    });
    tbls.forEach(function (t) { if (keep[t.dataset.t]) t.classList.add('on'); });
    show(name);
  }
  tbls.forEach(function (t) {
    t.addEventListener('click', function (ev) { ev.stopPropagation(); focus(t.dataset.t); });
    t.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); focus(t.dataset.t); } });
  });
  svg.addEventListener('click', clear);
  function toggle(id, target, cls) {
    document.getElementById(id).addEventListener('click', function () {
      var on = target.classList.toggle(cls); this.setAttribute('aria-pressed', on);
    });
  }
  toggle('fit', stage, 'fit'); toggle('hub', svg, 'hide-hub'); toggle('ver', svg, 'only-ver');
  document.getElementById('q').addEventListener('input', function (e) {
    var q = e.target.value.trim().toLowerCase();
    tbls.forEach(function (t) {
      var name = t.dataset.t, hit = !!q && (name.indexOf(q) >= 0 || DATA[name].columns.some(function (c) { return c.name.indexOf(q) >= 0; }));
      t.classList.toggle('hit', hit);
    });
  });
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
