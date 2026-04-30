#!/usr/bin/env python3
"""kb-price-mcp 스모크 테스트.

- kb_search_complex("잠실엘스") → COMPLEX_NO=15617
- kb_get_complex_basic("15617") → 단지명/세대수/평형 목록
- kb_get_complex_price("15617") → 전 평형 시세
- kb_get_complex_price_history("15617", "63146", years=2)

server 모듈을 import 해서 직접 코루틴 호출.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

# repo root 를 sys.path 에 추가
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import server  # noqa: E402
from kb_client import get_client  # noqa: E402


def _hr(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


def _show(s: str, max_chars: int = 4000) -> None:
    if len(s) <= max_chars:
        print(s)
    else:
        print(s[:max_chars])
        print(f"... (truncated, total {len(s)} chars)")


async def main() -> None:
    try:
        _hr("1. kb_search_complex('잠실엘스')")
        s1 = await server.kb_search_complex("잠실엘스", limit=3)
        _show(s1, 3000)
        d1 = json.loads(s1)
        first = (d1.get("results") or [{}])[0]
        complex_no = first.get("complex_no") or "15617"
        rep_area = str(first.get("rep_area_no") or "63146")
        print(f"  → complex_no={complex_no}, rep_area_no={rep_area}")

        _hr(f"2. kb_get_complex_basic('{complex_no}')")
        s2 = await server.kb_get_complex_basic(complex_no)
        _show(s2, 5000)

        _hr(f"3. kb_get_complex_price('{complex_no}')  -- fan-out across area_no")
        s3 = await server.kb_get_complex_price(complex_no)
        _show(s3, 6000)

        _hr(f"4. kb_get_complex_price_history('{complex_no}', '{rep_area}', years=2)")
        s4 = await server.kb_get_complex_price_history(complex_no, rep_area, years=2)
        _show(s4, 6000)

    finally:
        await get_client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
