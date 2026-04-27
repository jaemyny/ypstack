#!/usr/bin/env python3
"""Confluence 레이블 관리 MCP 서버"""

import os
import base64
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("confluence-label-mcp")


def _headers() -> dict:
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("CONFLUENCE_TOKEN", "")
    if not email or not token:
        raise ValueError("CONFLUENCE_EMAIL 또는 CONFLUENCE_TOKEN 환경변수가 설정되지 않았습니다.")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _base_url() -> str:
    url = os.environ.get("CONFLUENCE_URL", "")
    if not url:
        raise ValueError("CONFLUENCE_URL 환경변수가 설정되지 않았습니다.")
    return url.rstrip("/")


@mcp.tool()
def get_labels(page_id: str) -> str:
    """Confluence 페이지의 현재 레이블 목록을 조회합니다.

    Args:
        page_id: Confluence 페이지 ID (예: 2149286590)
    """
    try:
        url = f"{_base_url()}/rest/api/content/{page_id}/label"
        with httpx.Client(timeout=10) as client:
            res = client.get(url, headers=_headers())
            res.raise_for_status()

        labels = res.json().get("results", [])
        if not labels:
            return f"페이지 {page_id}에 레이블이 없습니다."
        names = [lb["name"] for lb in labels]
        return f"페이지 {page_id} 레이블 ({len(names)}개): {', '.join(names)}"

    except httpx.HTTPStatusError as e:
        return f"오류 (HTTP {e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"오류: {e}"


@mcp.tool()
def add_labels(page_id: str, labels: list[str]) -> str:
    """Confluence 페이지에 레이블을 추가합니다.

    Args:
        page_id: Confluence 페이지 ID (예: 2149286590)
        labels: 추가할 레이블 이름 목록 (예: ["status-verified", "lvl3-expert"])
    """
    try:
        url = f"{_base_url()}/rest/api/content/{page_id}/label"
        body = [{"prefix": "global", "name": lb} for lb in labels]
        with httpx.Client(timeout=10) as client:
            res = client.post(url, headers=_headers(), json=body)
            res.raise_for_status()

        all_labels = [lb["name"] for lb in res.json().get("results", [])]
        added = ", ".join(labels)
        current = ", ".join(all_labels) if all_labels else "(없음)"
        return f"레이블 추가 완료: {added}\n현재 전체 레이블: {current}"

    except httpx.HTTPStatusError as e:
        return f"오류 (HTTP {e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"오류: {e}"


@mcp.tool()
def remove_label(page_id: str, label: str) -> str:
    """Confluence 페이지에서 특정 레이블을 삭제합니다.

    Args:
        page_id: Confluence 페이지 ID (예: 2149286590)
        label: 삭제할 레이블 이름 (예: "status-draft")
    """
    try:
        url = f"{_base_url()}/rest/api/content/{page_id}/label/{label}"
        with httpx.Client(timeout=10) as client:
            res = client.delete(url, headers=_headers())
            if res.status_code == 404:
                return f"페이지 {page_id}에 레이블 '{label}'이 존재하지 않습니다."
            res.raise_for_status()

        return f"레이블 '{label}' 삭제 완료 (페이지 {page_id})"

    except httpx.HTTPStatusError as e:
        return f"오류 (HTTP {e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"오류: {e}"


if __name__ == "__main__":
    mcp.run()
