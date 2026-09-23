#!/usr/bin/env python3
"""Render the Aeropress experiments Notion page as a page on the site."""

import html
import json
import os
import time
import urllib.error
import urllib.request


NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_PAGE_ID = os.environ.get(
    "NOTION_AEROPRESS_PAGE_ID", "3e202030da15800e8ea8f1091728b540"
).replace("-", "")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def notion_request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data,
        headers=HEADERS,
        method="POST" if body is not None else "GET",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Notion API {error.code} for {path}: {detail}") from error
            time.sleep(2**attempt)
        except urllib.error.URLError:
            if attempt == 3:
                raise
            time.sleep(2**attempt)


def rich_text(value):
    parts = []
    for item in value or []:
        if item.get("type") == "equation":
            text = f'\\({html.escape(item["equation"]["expression"])}\\)'
        else:
            text = html.escape(item.get("plain_text", "")).replace("\n", "<br>")
        annotations = item.get("annotations", {})
        if annotations.get("code"):
            text = f"<code>{text}</code>"
        if annotations.get("bold"):
            text = f"<strong>{text}</strong>"
        if annotations.get("italic"):
            text = f"<em>{text}</em>"
        if annotations.get("strikethrough"):
            text = f"<s>{text}</s>"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        href = item.get("href")
        if href:
            text = f'<a href="{html.escape(href, quote=True)}">{text}</a>'
        parts.append(text)
    return "".join(parts)


def plain_text(value):
    return "".join(item.get("plain_text", "") for item in value or [])


def fetch_children(block_id):
    blocks = []
    cursor = None
    while True:
        suffix = f"?start_cursor={cursor}" if cursor else ""
        result = notion_request(f"/blocks/{block_id}/children{suffix}")
        blocks.extend(result.get("results", []))
        if not result.get("has_more"):
            return blocks
        cursor = result["next_cursor"]


def query_database(database_id):
    pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        result = notion_request(f"/databases/{database_id}/query", body)
        pages.extend(result.get("results", []))
        if not result.get("has_more"):
            return pages
        cursor = result["next_cursor"]


def property_text(prop):
    kind = prop.get("type", "")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return rich_text(value)
    if kind in ("select", "status"):
        return html.escape((value or {}).get("name", ""))
    if kind == "multi_select":
        return ", ".join(html.escape(item.get("name", "")) for item in value or [])
    if kind == "date":
        if not value:
            return ""
        start = html.escape(value.get("start", ""))
        end = html.escape(value.get("end", ""))
        return f"{start} – {end}" if end else start
    if kind == "number":
        return "" if value is None else html.escape(str(value))
    if kind == "checkbox":
        return "✓" if value else ""
    if kind in ("url", "email", "phone_number"):
        if not value:
            return ""
        url = value if kind == "url" else f"{kind.split('_')[0]}:{value}"
        return f'<a href="{html.escape(url, quote=True)}">{html.escape(value)}</a>'
    if kind in ("created_time", "last_edited_time"):
        return html.escape(value or "")
    if kind in ("created_by", "last_edited_by"):
        return html.escape((value or {}).get("name", ""))
    if kind == "people":
        return ", ".join(html.escape(person.get("name", "")) for person in value or [])
    if kind == "files":
        links = []
        for item in value or []:
            source = item.get(item.get("type", ""), {}).get("url")
            if source:
                links.append(
                    f'<a href="{html.escape(source, quote=True)}">{html.escape(item.get("name", "file"))}</a>'
                )
        return ", ".join(links)
    if kind in ("formula", "rollup") and isinstance(value, dict):
        subtype = value.get("type")
        inner = value.get(subtype)
        return "" if inner is None else html.escape(str(inner))
    return ""


def database_html(database_id, title=""):
    database = notion_request(f"/databases/{database_id}")
    pages = query_database(database_id)
    properties = database.get("properties", {})
    names = list(properties)
    title_names = [name for name in names if properties[name].get("type") == "title"]
    names = title_names + [name for name in names if name not in title_names]
    heading = title or plain_text(database.get("title", []))
    rows = []
    for page in pages:
        cells = "".join(
            f"<td>{property_text(page.get('properties', {}).get(name, {}))}</td>"
            for name in names
        )
        rows.append(f"<tr>{cells}</tr>")
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        + "".join(f"<th>{html.escape(name)}</th>" for name in names)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )
    return (f"<h2>{html.escape(heading)}</h2>" if heading else "") + table


def blocks_html(blocks):
    output = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        kind = block.get("type", "")
        data = block.get(kind, {})

        if kind in ("bulleted_list_item", "numbered_list_item"):
            tag = "ul" if kind == "bulleted_list_item" else "ol"
            items = []
            while index < len(blocks) and blocks[index].get("type") == kind:
                item = blocks[index]
                item_data = item[kind]
                content = rich_text(item_data.get("rich_text", []))
                if item.get("has_children"):
                    content += blocks_html(fetch_children(item["id"]))
                items.append(f"<li>{content}</li>")
                index += 1
            output.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        if kind == "paragraph":
            content = rich_text(data.get("rich_text", []))
            if content:
                output.append(f"<p>{content}</p>")
        elif kind in ("heading_1", "heading_2", "heading_3"):
            level = kind[-1]
            output.append(f"<h{level}>{rich_text(data.get('rich_text', []))}</h{level}>")
        elif kind == "to_do":
            checked = " checked" if data.get("checked") else ""
            output.append(
                f'<p class="todo"><input type="checkbox" disabled{checked}> '
                f'{rich_text(data.get("rich_text", []))}</p>'
            )
        elif kind in ("quote", "callout"):
            content = rich_text(data.get("rich_text", []))
            if block.get("has_children"):
                content += blocks_html(fetch_children(block["id"]))
            tag = "blockquote" if kind == "quote" else "aside"
            output.append(f"<{tag}>{content}</{tag}>")
        elif kind == "toggle":
            children = blocks_html(fetch_children(block["id"])) if block.get("has_children") else ""
            output.append(
                f"<details><summary>{rich_text(data.get('rich_text', []))}</summary>{children}</details>"
            )
        elif kind == "divider":
            output.append("<hr>")
        elif kind == "equation":
            output.append(f'<p>\\[{html.escape(data.get("expression", ""))}\\]</p>')
        elif kind == "code":
            language = html.escape(data.get("language", ""), quote=True)
            output.append(
                f'<pre><code data-language="{language}">{html.escape(plain_text(data.get("rich_text", [])))}</code></pre>'
            )
        elif kind == "table":
            rows = fetch_children(block["id"])
            rendered_rows = []
            for row_number, row in enumerate(rows):
                cell_tag = "th" if data.get("has_column_header") and row_number == 0 else "td"
                cells = "".join(
                    f"<{cell_tag}>{rich_text(cell)}</{cell_tag}>"
                    for cell in row.get("table_row", {}).get("cells", [])
                )
                rendered_rows.append(f"<tr>{cells}</tr>")
            output.append(f'<div class="table-wrap"><table>{"".join(rendered_rows)}</table></div>')
        elif kind == "child_database":
            output.append(database_html(block["id"], data.get("title", "")))
        elif kind == "child_page":
            output.append(f'<p class="subpage">↳ {html.escape(data.get("title", "Untitled"))}</p>')
        elif kind in ("bookmark", "link_preview", "embed"):
            url = data.get("url", "")
            if url:
                safe_url = html.escape(url, quote=True)
                output.append(f'<p><a href="{safe_url}">{html.escape(url)}</a></p>')
        elif kind == "image":
            source = data.get(data.get("type", ""), {}).get("url")
            caption = plain_text(data.get("caption", []))
            if source:
                output.append(
                    f'<figure><img src="{html.escape(source, quote=True)}" alt="{html.escape(caption, quote=True)}">'
                    + (f"<figcaption>{html.escape(caption)}</figcaption>" if caption else "")
                    + "</figure>"
                )
        elif kind == "synced_block":
            source_id = (data.get("synced_from") or {}).get("block_id", block["id"])
            output.append(blocks_html(fetch_children(source_id)))

        if block.get("has_children") and kind not in (
            "bulleted_list_item", "numbered_list_item", "quote", "callout", "toggle",
            "table", "child_database", "synced_block"
        ):
            output.append(blocks_html(fetch_children(block["id"])))
        index += 1
    return "\n".join(output)


def page_document(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Aeropress experiments and brewing notes by Ishaan Ganti.">
    <title>{html.escape(title)} — Ishaan Ganti</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/scripts/theme.css">
    <script>var _t=localStorage.getItem('theme');if(_t)document.documentElement.setAttribute('data-theme',_t);</script>
    <style>
        :root {{ --bg:#fcfcf8; --text:#1f2937; --muted:#5b6470; --link:#1d4ed8; --border:rgba(31,41,55,.14); }}
        * {{ box-sizing:border-box; }}
        body {{ font-family:"Inter",system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); max-width:960px; margin:72px auto; padding:0 24px; line-height:1.65; font-size:17px; }}
        a {{ color:var(--link); text-decoration-thickness:1px; text-underline-offset:.18em; }}
        .back {{ margin:0 0 36px; font-size:.95rem; }}
        h1 {{ font-size:clamp(2rem,6vw,3.5rem); line-height:1.02; letter-spacing:-.04em; margin:0 0 14px; }}
        .lede {{ color:var(--muted); margin:0 0 44px; max-width:62ch; }}
        h2 {{ font-size:1.35rem; margin:38px 0 12px; }}
        h3 {{ font-size:1.1rem; margin:28px 0 8px; }}
        p {{ margin:0 0 16px; }}
        ul,ol {{ margin:0 0 18px; padding-left:25px; }}
        blockquote,aside {{ border-left:3px solid var(--border); margin:0 0 18px; padding:8px 16px; color:var(--muted); }}
        details {{ margin:0 0 16px; }} summary {{ cursor:pointer; font-weight:600; }}
        hr {{ border:0; border-top:1px solid var(--border); margin:32px 0; }}
        code {{ background:rgba(31,41,55,.07); padding:2px 5px; border-radius:4px; }}
        pre {{ overflow:auto; background:rgba(31,41,55,.07); padding:16px; border-radius:8px; }}
        pre code {{ padding:0; background:none; }}
        .table-wrap {{ overflow-x:auto; margin:0 0 28px; border:1px solid var(--border); border-radius:8px; }}
        table {{ border-collapse:collapse; width:100%; min-width:720px; font-size:.9rem; }}
        th,td {{ border-right:1px solid var(--border); border-bottom:1px solid var(--border); padding:10px 12px; text-align:left; vertical-align:top; }}
        th:last-child,td:last-child {{ border-right:0; }} tr:last-child td {{ border-bottom:0; }}
        th {{ background:rgba(31,41,55,.055); font-weight:600; white-space:nowrap; }}
        figure {{ margin:24px 0; }} img {{ max-width:100%; height:auto; border-radius:8px; }} figcaption {{ color:var(--muted); font-size:.85rem; }}
        .todo input {{ margin-right:7px; }} .subpage {{ color:var(--muted); }}
        @media (max-width:600px) {{ body {{ margin:40px auto; padding:0 18px; font-size:16px; }} .table-wrap {{ margin-left:-10px; margin-right:-10px; }} }}
    </style>
</head>
<body>
    <p class="back"><a href="/misc.html">← back to misc</a></p>
    <header><h1>{html.escape(title)}</h1><p class="lede">journal of my aeropress endeavors</p></header>
    <main>{body}</main>
    <script src="/scripts/theme.js"></script>
</body>
</html>
"""


def main():
    try:
        page = notion_request(f"/pages/{NOTION_PAGE_ID}")
        title = "Aeropress Experiments"
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = plain_text(prop.get("title", [])) or title
                break
        body = blocks_html(fetch_children(NOTION_PAGE_ID))
    except RuntimeError as page_error:
        try:
            database = notion_request(f"/databases/{NOTION_PAGE_ID}")
        except Exception:
            raise page_error
        title = plain_text(database.get("title", [])) or "Aeropress Experiments"
        body = database_html(NOTION_PAGE_ID)

    output_path = os.path.join(REPO_ROOT, "aeropress.html")
    with open(output_path, "w", encoding="utf-8") as output:
        output.write(page_document(title, body))
    print(f"Wrote aeropress.html from Notion page {NOTION_PAGE_ID}.")


if __name__ == "__main__":
    main()
