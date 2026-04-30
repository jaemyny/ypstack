"""KB부동산 비공식 API 클라이언트 (api.kbland.kr).

- httpx.AsyncClient 단일 인스턴스 재사용
- 매너 호출: 호출 사이 최소 0.3s 간격 (asyncio.Lock + monotonic)
- 5xx / 타임아웃 시 1회 재시도
- dataHeader.resultCode != "10000" 면 에러 dict 반환
- 응답이 JSON 이 아니거나 dataBody 비어 있으면 에러 dict 반환
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

import httpx

KB_BASE = "https://api.kbland.kr"

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)

MIN_INTERVAL = 0.3  # seconds between requests
TIMEOUT = 15.0


def _headers() -> dict[str, str]:
    return {
        "User-Agent": os.getenv("KB_USER_AGENT", DEFAULT_UA),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Origin": "https://kbland.kr",
        "Referer": "https://kbland.kr/",
    }


class KBClient:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=KB_BASE,
                headers=_headers(),
                timeout=TIMEOUT,
                http2=False,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _throttle(self) -> None:
        now = time.monotonic()
        wait = MIN_INTERVAL - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()

    async def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """KB API GET. 성공 시 dataBody.data 를 반환. 실패 시 {'error': ..., 'hint': ...}."""
        client = await self._get_client()

        async with self._lock:
            await self._throttle()
            try:
                r = await client.get(path, params=params)
            except (httpx.TimeoutException, httpx.TransportError):
                # 1회 재시도
                await asyncio.sleep(0.5)
                self._last_call = time.monotonic()
                try:
                    r = await client.get(path, params=params)
                except Exception as e:
                    return {"error": f"네트워크 오류: {type(e).__name__}: {e}", "path": path}

        if r.status_code >= 500:
            # 5xx 1회 재시도
            async with self._lock:
                await self._throttle()
                try:
                    r = await client.get(path, params=params)
                except Exception as e:
                    return {"error": f"재시도 실패: {type(e).__name__}: {e}", "path": path}

        if r.status_code != 200:
            return {
                "error": f"HTTP {r.status_code}",
                "path": path,
                "raw": (r.text or "")[:200],
            }

        try:
            payload = r.json()
        except ValueError:
            return {
                "error": "JSON 파싱 실패",
                "path": path,
                "raw": (r.text or "")[:200],
            }

        header = payload.get("dataHeader", {})
        result_code = header.get("resultCode")
        if result_code != "10000":
            return {
                "error": f"KB API 오류 resultCode={result_code}",
                "message": header.get("message", ""),
                "path": path,
            }

        body = payload.get("dataBody", {})
        if not body:
            return {"error": "빈 dataBody", "path": path, "hint": "파라미터를 확인해 주세요."}

        # dataBody.data 가 핵심 페이로드 (모든 5개 엔드포인트 공통)
        data = body.get("data")
        if data is None:
            return {"error": "dataBody.data 누락", "path": path}

        return {"data": data}


_client: Optional[KBClient] = None


def get_client() -> KBClient:
    global _client
    if _client is None:
        _client = KBClient()
    return _client
