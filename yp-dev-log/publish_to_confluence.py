#!/usr/bin/env python3
"""
Publish a markdown dev log to Confluence Cloud.

Usage:
    python publish_to_confluence.py <path-to-markdown>

Env vars (loaded from backend/.env if present, else from shell):
    CONFLUENCE_BASE_URL    e.g. https://weolbu-company.atlassian.net
    CONFLUENCE_USER_EMAIL  atlassian account email
    CONFLUENCE_API_TOKEN   atlassian API token

Constants:
    PARENT_PAGE_ID = "2095776641"
    SPACE_ID       = "1023181044"

Exit codes:
    0   success (created)
    1   usage / missing file
    2   duplicate page (same title already exists)
    3   API error
    10  Confluence env vars not set — publishing skipped (markdown-only mode)
"""
from __future__ import annotations

import base64
import html
import os
import re
import sys
from pathlib import Path

import requests

PARENT_PAGE_ID = "2095776641"
SPACE_ID = "1023181044"
# Loaded in order — later entries override earlier ones.
# Global secrets live under ~/.config/ypstack/.env (shared by every project);
# a project can override a single value via its local .env / backend/.env.
ENV_CANDIDATES = [
    Path.home() / ".config/ypstack/.env",  # global (shared across projects)
    Path.cwd() / "backend/.env",           # project-local override
    Path.cwd() / ".env",                   # project-root override
]


# ─────────────────────────────────────────────────────────────
# Env loading (minimal .env parser, no python-dotenv dependency)
# ─────────────────────────────────────────────────────────────
def load_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


PLACEHOLDER_TOKENS = {"발급받은_API_토큰", "발급받은_토큰", "your_token_here", "YOUR_TOKEN", ""}

SETUP_NOTICE = (
    "[info] Confluence 자동 게시를 사용하려면 아래 환경 변수를 설정하세요:\n"
    "  - CONFLUENCE_BASE_URL\n"
    "  - CONFLUENCE_USER_EMAIL\n"
    "  - CONFLUENCE_API_TOKEN\n"
    "설정 방법: ~/.claude/skills/ypstack/yp-dev-log/SKILL.md 참조\n"
    "이번에는 마크다운 파일만 생성되었습니다 (게시 스킵).\n"
)


def get_config() -> tuple[str, str, str]:
    env: dict[str, str] = {}
    for p in ENV_CANDIDATES:
        env.update(load_env_file(p))
    # Shell env overrides file env
    for k in ("CONFLUENCE_BASE_URL", "CONFLUENCE_USER_EMAIL", "CONFLUENCE_API_TOKEN"):
        if os.environ.get(k):
            env[k] = os.environ[k]

    base = env.get("CONFLUENCE_BASE_URL", "").rstrip("/")
    email = env.get("CONFLUENCE_USER_EMAIL", "")
    token = env.get("CONFLUENCE_API_TOKEN", "")

    if not base or not email or token in PLACEHOLDER_TOKENS:
        sys.stderr.write(SETUP_NOTICE)
        sys.exit(10)  # 10 = setup incomplete (not an error — publishing simply skipped)

    return base, email, token


def auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


# ─────────────────────────────────────────────────────────────
# Markdown → Confluence Storage Format (XHTML subset)
# ─────────────────────────────────────────────────────────────
INLINE_CODE_RE = re.compile(r"`([^`\n]+?)`")
BOLD_RE = re.compile(r"\*\*([^\*\n]+?)\*\*")
ITALIC_RE = re.compile(r"(?<![\*\w])\*([^\*\n]+?)\*(?!\w)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def render_inline(text: str) -> str:
    """Escape then apply bold/italic/code/link. Order matters."""
    # Protect code spans first — replace with placeholders
    code_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(match.group(1))
        return f"\x00CODE{len(code_spans) - 1}\x00"

    text = INLINE_CODE_RE.sub(stash_code, text)

    # Escape HTML
    text = html.escape(text, quote=False)

    # Bold, italic, links (order: bold before italic to avoid conflict)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITALIC_RE.sub(r"<em>\1</em>", text)
    text = LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', text)

    # Restore code spans with escape
    def restore_code(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return f"<code>{html.escape(code_spans[idx], quote=False)}</code>"

    text = re.sub(r"\x00CODE(\d+)\x00", restore_code, text)
    return text


def split_table_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = split_table_row(stripped)
    return all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c)


def markdown_to_storage(md: str) -> tuple[str, str | None]:
    """Convert markdown to Confluence storage format. Returns (xhtml, first_h1_title)."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    title: str | None = None

    in_code = False
    code_lang = ""
    code_buf: list[str] = []

    # List state
    list_stack: list[tuple[str, int]] = []  # (tag, indent)

    def close_lists(to_indent: int = -1) -> None:
        while list_stack and list_stack[-1][1] > to_indent:
            tag, _ = list_stack.pop()
            out.append(f"</{tag}>")

    def ensure_list(tag: str, indent: int) -> None:
        # Close deeper/different lists at same indent
        while list_stack and (list_stack[-1][1] > indent or (list_stack[-1][1] == indent and list_stack[-1][0] != tag)):
            t, _ = list_stack.pop()
            out.append(f"</{t}>")
        if not list_stack or list_stack[-1][1] < indent:
            list_stack.append((tag, indent))
            out.append(f"<{tag}>")

    while i < n:
        line = lines[i]

        # Fenced code block
        fence_match = re.match(r"^```(\w*)\s*$", line)
        if fence_match and not in_code:
            close_lists()
            in_code = True
            code_lang = fence_match.group(1)
            code_buf = []
            i += 1
            continue
        if in_code:
            if line.strip() == "```":
                in_code = False
                code_body = "\n".join(code_buf)
                lang_attr = f'<ac:parameter ac:name="language">{html.escape(code_lang or "none")}</ac:parameter>' if code_lang else ""
                out.append(
                    f'<ac:structured-macro ac:name="code">{lang_attr}'
                    f'<ac:plain-text-body><![CDATA[{code_body}]]></ac:plain-text-body>'
                    f'</ac:structured-macro>'
                )
                code_buf = []
                code_lang = ""
            else:
                code_buf.append(line)
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^---+\s*$", line):
            close_lists()
            out.append("<hr/>")
            i += 1
            continue

        # Headings (# through ######)
        heading_match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if heading_match:
            close_lists()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            if level == 1 and title is None:
                title = re.sub(r"[`*_]", "", text).strip()
            out.append(f"<h{level}>{render_inline(text)}</h{level}>")
            i += 1
            continue

        # Table: header row + separator + body rows
        if line.strip().startswith("|") and i + 1 < n and is_table_separator(lines[i + 1]):
            close_lists()
            header = split_table_row(line)
            i += 2  # skip header + separator
            rows: list[list[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i]))
                i += 1
            out.append("<table><tbody>")
            out.append("<tr>" + "".join(f"<th>{render_inline(c)}</th>" for c in header) + "</tr>")
            for r in rows:
                # Pad/truncate to header length
                while len(r) < len(header):
                    r.append("")
                r = r[: len(header)]
                out.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            continue

        # Blockquote
        if line.lstrip().startswith(">"):
            close_lists()
            quote_lines = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            body = " ".join(render_inline(q) for q in quote_lines if q.strip())
            out.append(f"<blockquote><p>{body}</p></blockquote>")
            continue

        # Unordered list
        ul_match = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if ul_match:
            indent = len(ul_match.group(1))
            content = ul_match.group(2)
            ensure_list("ul", indent)
            out.append(f"<li>{render_inline(content)}</li>")
            i += 1
            continue

        # Ordered list
        ol_match = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if ol_match:
            indent = len(ol_match.group(1))
            content = ol_match.group(2)
            ensure_list("ol", indent)
            out.append(f"<li>{render_inline(content)}</li>")
            i += 1
            continue

        # Blank line → close lists, emit nothing
        if not line.strip():
            close_lists()
            i += 1
            continue

        # Paragraph (collect consecutive non-blank, non-special lines)
        close_lists()
        para: list[str] = [line]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            if re.match(r"^#{1,6}\s", nxt) or nxt.lstrip().startswith(">") or re.match(r"^(\s*)[-*]\s", nxt) or re.match(r"^(\s*)\d+\.\s", nxt):
                break
            if nxt.strip().startswith("|"):
                break
            if nxt.startswith("```"):
                break
            if re.match(r"^---+\s*$", nxt):
                break
            para.append(nxt)
            i += 1
        body = "<br/>".join(render_inline(p) for p in para)
        out.append(f"<p>{body}</p>")

    if in_code:
        # Dangling code fence — flush as-is
        code_body = "\n".join(code_buf)
        out.append(
            f'<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[{code_body}]]></ac:plain-text-body></ac:structured-macro>'
        )
    close_lists()
    return "\n".join(out), title


# ─────────────────────────────────────────────────────────────
# Confluence API calls
# ─────────────────────────────────────────────────────────────
def find_page_by_title(base: str, auth: str, title: str) -> dict | None:
    """Return an *active* (status=current) child of PARENT_PAGE_ID whose title matches, or None.

    Iterating PARENT_PAGE_ID's children is more reliable than the space-level title filter,
    which can miss titles containing brackets / em-dash / non-ASCII characters. Also filters
    out trashed pages (Confluence soft-deletes).
    """
    headers = {"Authorization": auth, "Accept": "application/json"}
    url = f"{base}/wiki/api/v2/pages/{PARENT_PAGE_ID}/children"
    cursor_url: str | None = url + "?limit=250"
    while cursor_url:
        r = requests.get(cursor_url, headers=headers, timeout=20)
        if r.status_code != 200:
            sys.stderr.write(f"[find] {r.status_code}: {r.text[:300]}\n")
            return None
        data = r.json()
        for page in data.get("results", []):
            if page.get("title") != title:
                continue
            # Verify active (not trashed) via a direct fetch
            page_id = page.get("id")
            rr = requests.get(f"{base}/wiki/api/v2/pages/{page_id}", headers=headers, timeout=15)
            if rr.status_code == 200 and rr.json().get("status") == "current":
                return rr.json()
        next_link = (data.get("_links") or {}).get("next")
        cursor_url = (base + next_link) if next_link else None
    return None


def create_page(base: str, auth: str, title: str, storage: str) -> dict:
    url = f"{base}/wiki/api/v2/pages"
    headers = {"Authorization": auth, "Content-Type": "application/json", "Accept": "application/json"}
    body = {
        "spaceId": SPACE_ID,
        "status": "current",
        "title": title,
        "parentId": PARENT_PAGE_ID,
        "body": {"representation": "storage", "value": storage},
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code not in (200, 201):
        sys.stderr.write(f"[create] {r.status_code}: {r.text[:500]}\n")
        sys.exit(3)
    return r.json()


def page_web_url(base: str, page: dict) -> str:
    webui = (page.get("_links") or {}).get("webui", "")
    if webui:
        return f"{base}/wiki{webui}"
    page_id = page.get("id", "")
    return f"{base}/wiki/spaces/~/pages/{page_id}" if page_id else ""


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write(__doc__ or "")
        sys.exit(1)

    md_path = Path(sys.argv[1]).expanduser().resolve()
    if not md_path.is_file():
        sys.stderr.write(f"[file] not found: {md_path}\n")
        sys.exit(1)

    base, email, token = get_config()
    auth = auth_header(email, token)

    md = md_path.read_text(encoding="utf-8")
    storage, first_h1 = markdown_to_storage(md)
    title = first_h1 or md_path.stem

    print(f"[info] title: {title}")
    print(f"[info] source: {md_path}")
    print(f"[info] target: {base}/wiki  (space={SPACE_ID}, parent={PARENT_PAGE_ID})")

    existing = find_page_by_title(base, auth, title)
    if existing:
        url = page_web_url(base, existing)
        print(f"[skip] 이미 존재합니다: '{title}' → {url}")
        sys.exit(2)

    created = create_page(base, auth, title, storage)
    url = page_web_url(base, created)
    print(f"[ok] 게시 완료: {url}")
    sys.exit(0)


if __name__ == "__main__":
    main()
