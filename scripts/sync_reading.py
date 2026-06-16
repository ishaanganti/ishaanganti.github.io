#!/usr/bin/env python3
import html
import json
import os
import re
import urllib.request
from datetime import datetime

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def notion_get(path):
    req = urllib.request.Request(f"https://api.notion.com/v1{path}", headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def notion_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}", data=data, headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def plain_text(rich_text):
    return "".join(t["plain_text"] for t in rich_text)


def rich_to_html(rich_text):
    parts = []
    for t in rich_text:
        if t.get("type") == "equation":
            parts.append(f'\\({t["equation"]["expression"]}\\)')
            continue
        text = html.escape(t["plain_text"])
        ann = t.get("annotations", {})
        if ann.get("bold"):
            text = f"<strong>{text}</strong>"
        if ann.get("italic"):
            text = f"<em>{text}</em>"
        if ann.get("code"):
            text = f"<code>{text}</code>"
        if t.get("href"):
            text = f'<a href="{html.escape(t["href"])}">{text}</a>'
        parts.append(text)
    return "".join(parts)


def blocks_to_html(blocks):
    out = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        t = b["type"]
        if t == "paragraph":
            text = rich_to_html(b["paragraph"]["rich_text"])
            if text.strip():
                out.append(f"<p>{text}</p>")
        elif t in ("heading_1", "heading_2", "heading_3"):
            lvl = t[-1]
            out.append(f"<h{lvl}>{rich_to_html(b[t]['rich_text'])}</h{lvl}>")
        elif t == "bulleted_list_item":
            items = []
            while i < len(blocks) and blocks[i]["type"] == "bulleted_list_item":
                b2 = blocks[i]
                text = rich_to_html(b2["bulleted_list_item"]["rich_text"])
                if b2.get("has_children"):
                    text += blocks_to_html(fetch_blocks(b2["id"]))
                items.append(f"<li>{text}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
            continue
        elif t == "numbered_list_item":
            items = []
            while i < len(blocks) and blocks[i]["type"] == "numbered_list_item":
                b2 = blocks[i]
                text = rich_to_html(b2["numbered_list_item"]["rich_text"])
                if b2.get("has_children"):
                    text += blocks_to_html(fetch_blocks(b2["id"]))
                items.append(f"<li>{text}</li>")
                i += 1
            out.append(f"<ol>{''.join(items)}</ol>")
            continue
        elif t == "equation":
            out.append(f"<p>\\[{b['equation']['expression']}\\]</p>")
        elif t == "quote":
            out.append(f"<blockquote>{rich_to_html(b['quote']['rich_text'])}</blockquote>")
        elif t == "divider":
            out.append("<hr>")
        i += 1
    return "\n".join(out)


def fetch_blocks(page_id):
    blocks, cursor = [], None
    while True:
        path = f"/blocks/{page_id}/children"
        if cursor:
            path += f"?start_cursor={cursor}"
        result = notion_get(path)
        blocks.extend(result["results"])
        if not result.get("has_more"):
            break
        cursor = result["next_cursor"]
    return blocks


def fetch_database():
    pages, cursor = [], None
    while True:
        body = {"sorts": [{"property": "Date Read", "direction": "descending"}]}
        if cursor:
            body["start_cursor"] = cursor
        result = notion_post(f"/databases/{NOTION_DB_ID}/query", body)
        pages.extend(result["results"])
        if not result.get("has_more"):
            break
        cursor = result["next_cursor"]
    return pages


def note_page(title, author, date_str, reading_type, body_html):
    meta = " &middot; ".join(filter(None, [html.escape(author), html.escape(reading_type), html.escape(date_str)]))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} — Ishaan Ganti</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/scripts/theme.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <script>var _t=localStorage.getItem('theme');if(_t)document.documentElement.setAttribute('data-theme',_t);</script>
    <style>
        :root {{
            --bg: #fcfcf8;
            --text: #1f2937;
            --muted: #5b6470;
            --link: #1d4ed8;
            --border: rgba(29, 78, 216, 0.25);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: "Inter", system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            max-width: 680px;
            margin: 72px auto;
            padding: 0 24px;
            line-height: 1.65;
            font-size: 18px;
        }}
        a {{ color: var(--link); text-decoration-thickness: 1px; text-underline-offset: 0.18em; text-decoration-color: var(--border); }}
        a:hover {{ text-decoration-color: var(--link); }}
        .back {{ font-size: 0.95rem; margin-bottom: 40px; }}
        .back a {{ color: var(--muted); }}
        h1 {{ font-size: clamp(1.6rem, 5vw, 2.2rem); line-height: 1.1; margin: 0 0 8px; font-weight: 700; letter-spacing: -0.02em; }}
        .meta {{ font-size: 0.95rem; color: var(--muted); margin: 0 0 40px; }}
        h2 {{ font-size: 1.2rem; font-weight: 600; margin: 36px 0 8px; }}
        h3 {{ font-size: 1.05rem; font-weight: 600; margin: 24px 0 6px; }}
        p {{ margin: 0 0 16px; }}
        ul, ol {{ margin: 0 0 16px; padding-left: 24px; }}
        li {{ margin-bottom: 4px; }}
        li ul, li ol {{ margin: 4px 0 0; }}
        blockquote {{ border-left: 3px solid var(--border); margin: 0 0 16px; padding: 4px 0 4px 16px; color: var(--muted); font-style: italic; }}
        hr {{ border: none; border-top: 1px solid rgba(31,41,55,0.1); margin: 32px 0; }}
        code {{ font-family: monospace; font-size: 0.88em; background: rgba(31,41,55,0.06); padding: 1px 4px; border-radius: 3px; }}
        @media (max-width: 600px) {{ body {{ margin: 40px auto; font-size: 17px; }} }}
    </style>
</head>
<body>
    <p class="back"><a href="/#reading-heading">← back</a></p>
    <h1>{html.escape(title)}</h1>
    <p class="meta">{meta}</p>
    {body_html}
    <script src="/scripts/theme.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.body,{{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'\\\\(',right:'\\\\)',display:false}},{{left:'\\\\[',right:'\\\\]',display:true}}]}})"></script>
</body>
</html>"""


def reading_list_html(entries):
    if not entries:
        return (
            '<ul class="reading-list" id="reading-list">'
            '<li class="reading-item" style="color:var(--muted);font-size:0.95rem;border:none;">Nothing here yet.</li>'
            '</ul>'
        )
    items = []
    for e in entries:
        type_esc = html.escape(e["type"])
        type_slug = slugify(e["type"]) if e["type"] else ""
        tag_html = f'<span class="tag tag-{type_slug}">{type_esc}</span> ' if type_esc else ""
        date_esc = html.escape(e["date_str"])
        meta_text = f"{tag_html}{date_esc}" if date_esc else tag_html

        title_esc = html.escape(e["title"])
        url = e.get("url", "")
        if url:
            title_html = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{title_esc}</a>'
        else:
            title_html = title_esc

        pen = (
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>'
            '</svg>'
        )
        indicator = (
            f'<a href="/readings/{e["slug"]}/" class="notes-icon" title="My notes">{pen}</a>'
            if e["has_notes"] else ""
        )
        author_html = f'<span class="reading-author">{html.escape(e["author"])}</span>' if e["author"] else ""
        items.append(
            f'<li class="reading-item"'
            f' data-type="{type_esc}"'
            f' data-date="{html.escape(e["date_raw"])}"'
            f' data-has-notes="{str(e["has_notes"]).lower()}">'
            f'<span class="reading-indicator">{indicator}</span>'
            f'<span class="reading-left"><span class="reading-title">{title_html}</span>{author_html}</span>'
            f'<span class="reading-meta">{meta_text}</span>'
            f'</li>'
        )
    return '<ul class="reading-list" id="reading-list">' + "".join(items) + "</ul>"


def update_index(list_html):
    index_path = os.path.join(REPO_ROOT, "index.html")
    with open(index_path) as f:
        src = f.read()

    pattern = re.compile(
        r"<!-- READING_LIST_ITEMS_START -->.*?<!-- READING_LIST_ITEMS_END -->", re.DOTALL
    )
    replacement = (
        "<!-- READING_LIST_ITEMS_START -->\n"
        f"            {list_html}\n"
        "            <!-- READING_LIST_ITEMS_END -->"
    )
    src = pattern.sub(replacement, src)

    with open(index_path, "w") as f:
        f.write(src)


def main():
    pages = fetch_database()
    print(f"Found {len(pages)} pages in database.")

    entries = []
    for page in pages:
        props = page["properties"]
        title = plain_text(props.get("Title", {}).get("title", []))
        author = plain_text(props.get("Author", {}).get("rich_text", []))
        date_val = props.get("Date Read", {}).get("date")
        has_notes = props.get("Has Notes", {}).get("checkbox", False)

        if not title:
            continue

        if date_val:
            try:
                date_obj = datetime.fromisoformat(date_val["start"])
                date_str = date_obj.strftime("%B %-d, %Y")
                date_raw = date_val["start"]
            except Exception:
                date_str = date_val["start"]
                date_raw = date_val["start"]
        else:
            date_str = ""
            date_raw = ""

        type_prop = props.get("Type") or props.get("Multi-select") or {}
        type_vals = type_prop.get("multi_select", [])
        reading_type = type_vals[0]["name"] if type_vals else ""

        url = props.get("URL", {}).get("url") or ""

        slug = slugify(title)
        entries.append(
            {"title": title, "author": author, "date_str": date_str, "date_raw": date_raw,
             "slug": slug, "has_notes": has_notes, "page_id": page["id"], "type": reading_type,
             "url": url}
        )

        if has_notes:
            blocks = fetch_blocks(page["id"])
            body = blocks_to_html(blocks)
            out_dir = os.path.join(REPO_ROOT, "readings", slug)
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "index.html"), "w") as f:
                f.write(note_page(title, author, date_str, reading_type, body))
            print(f"  Wrote readings/{slug}/index.html")

    update_index(reading_list_html(entries))
    print(f"Done — {len(entries)} entries written to index.html.")


if __name__ == "__main__":
    main()
