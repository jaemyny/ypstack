"""
stats-biz-mcp: 소상공인 상가정보 + 서울 유동인구 + 한국부동산원 상업용부동산 MCP 서버
"""
import json
import os
from typing import Optional, Union

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stats-biz")

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _data_go_key() -> str:
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        raise ValueError("DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _seoul_key() -> str:
    key = os.environ.get("SEOUL_API_KEY", "")
    if not key:
        raise ValueError("SEOUL_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _reb_key() -> str:
    key = os.environ.get("REB_API_KEY", "")
    if not key:
        raise ValueError("REB_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


SEMAS_BASE = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeList"
_SEMAS_DEPRECATED_MSG = (
    "소상공인 상가정보 API(B553077)가 서비스 종료되어 데이터를 불러올 수 없습니다. "
    "소상공인시장진흥공단 빅데이터(bigdata.sbiz.or.kr)에서 시각화 서비스는 이용 가능합니다. "
    "JSON 데이터 API 대체 여부는 현재 확인 중입니다."
)


async def _get(url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _parse_semas_items(data: dict) -> list[dict]:
    """소상공인 API 응답에서 상가 목록 추출."""
    try:
        items = data["body"]["items"]["item"]
    except (KeyError, TypeError):
        return []
    if isinstance(items, dict):
        items = [items]
    return items if isinstance(items, list) else []


def _format_store(r: dict) -> dict:
    return {
        "bizesNm": r.get("bizesNm", ""),
        "brchNm": r.get("brchNm", ""),
        "indsLclsNm": r.get("indsLclsNm", ""),
        "indsMclsNm": r.get("indsMclsNm", ""),
        "lnoAdr": r.get("lnoAdr", ""),
        "lat": r.get("lat", ""),
        "lon": r.get("lon", ""),
    }


# ---------------------------------------------------------------------------
# 도구 1: semas_search_stores_by_district
# ---------------------------------------------------------------------------

@mcp.tool()
async def semas_search_stores_by_district(
    bjdong_cd: str,
    industry_class: Optional[str] = None,
    limit: Optional[int] = 100,
) -> str:
    """
    법정동코드 기준 상가(점포) 목록 조회.

    Args:
        bjdong_cd: 법정동코드 앞 5~8자리 (예: "11230" = 강남구, "11500" = 강서구)
        industry_class: 업종 대분류명 필터 (예: "음식점", "소매", "서비스"). 미입력 시 전체
        limit: 최대 반환 건수 (기본 100)

    Returns:
        JSON 문자열 — {bjdong_cd, industry_filter, count, stores:[{bizesNm, indsLclsNm, indsMclsNm, lnoAdr, lat, lon}]}
    """
    return json.dumps(
        {"error": _SEMAS_DEPRECATED_MSG, "bjdong_cd": bjdong_cd},
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# 도구 2: semas_get_store_stats_by_region
# ---------------------------------------------------------------------------

@mcp.tool()
async def semas_get_store_stats_by_region(
    bjdong_cd: str,
    top_n: Optional[int] = 10,
) -> str:
    """
    법정동코드 기준 업종 대분류별 상가 분포 통계.

    Args:
        bjdong_cd: 법정동코드 앞 5~8자리
        top_n: 상위 N개 업종 반환 (기본 10)

    Returns:
        JSON 문자열 — {bjdong_cd, total_stores, top_industries:[{industry, count, ratio_pct}]}
    """
    return json.dumps(
        {"error": _SEMAS_DEPRECATED_MSG, "bjdong_cd": bjdong_cd},
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# 도구 3: semas_search_commercial_area
# ---------------------------------------------------------------------------

@mcp.tool()
async def semas_search_commercial_area(
    area_name: str,
    limit: Optional[int] = 50,
) -> str:
    """
    상권명 기준 상가 목록 조회.

    Args:
        area_name: 상권명 (예: "홍대", "강남역", "명동")
        limit: 최대 반환 건수 (기본 50)

    Returns:
        JSON 문자열 — {area_name, count, stores:[{bizesNm, indsLclsNm, indsMclsNm, lnoAdr, lat, lon}]}
    """
    return json.dumps(
        {"error": _SEMAS_DEPRECATED_MSG, "area_name": area_name},
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# 도구 4: seoul_get_floating_population
# ---------------------------------------------------------------------------

@mcp.tool()
async def seoul_get_floating_population(
    date: str,
    area_code: Optional[Union[str, int]] = None,
) -> str:
    """
    서울시 자치구별 일별 유동인구 조회 (서울 열린데이터광장).

    Args:
        date: 조회일 YYYYMMDD (예: "20240101")
        area_code: 자치구 코드 필터 (예: "11680" = 강남구). 미입력 시 전체 자치구

    Returns:
        JSON 문자열 — {date, area_filter, count, data:[{STDR_DE, SIGNGU_CD, SIGNGU_NM, TOT_LVPOP_CO}]}
    """
    area_code = str(area_code) if area_code is not None else None
    try:
        key = _seoul_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    url = f"http://openapi.seoul.go.kr:8088/{key}/json/SPOP_DAILYSUM_JACHI/1/100/{date}/"
    try:
        data = await _get(url)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    # 서울 API 오류 응답 처리
    if "RESULT" in data:
        result_info = data["RESULT"]
        code = result_info.get("CODE", "")
        msg = result_info.get("MESSAGE", "")
        if not code.startswith("INFO"):
            return json.dumps(
                {"error": f"서울 API 오류 [{code}]: {msg}"},
                ensure_ascii=False,
            )

    rows = data.get("SPOP_DAILYSUM_JACHI", {}).get("row", [])
    if isinstance(rows, dict):
        rows = [rows]

    if area_code:
        rows = [r for r in rows if r.get("SIGNGU_CODE_SE", r.get("SIGNGU_CD", "")) == str(area_code)]

    records = [
        {
            "date": r.get("STDR_DE_ID", r.get("STDR_DE", "")),
            "area_code": r.get("SIGNGU_CODE_SE", r.get("SIGNGU_CD", "")),
            "area_name": r.get("SIGNGU_NM", ""),
            "total_population": r.get("TOT_LVPOP_CO", ""),
        }
        for r in rows
    ]

    result = {
        "date": date,
        "area_filter": area_code,
        "count": len(records),
        "data": records,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 5: reb_get_commercial_rent
# ---------------------------------------------------------------------------

@mcp.tool()
async def reb_get_commercial_rent(
    year_month: str,
    region: Optional[str] = None,
) -> str:
    """
    한국부동산원 상업용부동산 임대동향 조회.

    Args:
        year_month: 기준 연월 YYYYMM (예: "202401")
        region: 지역명 필터 (예: "서울", "경기"). 미입력 시 전국

    Returns:
        JSON 문자열 — {year_month, region_filter, count, data:[...]}
    """
    try:
        key = _reb_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    url = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
    params = {
        "serviceKey": key,
        "numOfRows": 100,
        "pageNo": 1,
        "STAT_YM": year_month,
        "_type": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            # JSON 응답 처리
            if "json" in content_type or resp.text.lstrip().startswith("{"):
                try:
                    data = resp.json()
                except Exception:
                    return json.dumps(
                        {"error": "JSON 파싱 실패", "raw": resp.text[:500]},
                        ensure_ascii=False,
                    )

                # 공통 응답 구조 탐색
                rows = []
                for key_name in ("SttsApiTblData", "response", "items"):
                    if key_name in data:
                        sub = data[key_name]
                        if isinstance(sub, dict):
                            rows = sub.get("row", sub.get("item", []))
                        elif isinstance(sub, list):
                            rows = sub
                        break
                if not rows and isinstance(data, list):
                    rows = data

            # XML/기타 응답 처리 (간이 파싱)
            else:
                import re
                items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)
                rows = []
                for item_xml in items:
                    pairs = re.findall(r"<(\w+)>(.*?)</\1>", item_xml)
                    rows.append({k: v for k, v in pairs})

    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    if isinstance(rows, dict):
        rows = [rows]

    if region:
        rows = [
            r for r in rows
            if region in str(r.get("REGION_NM", r.get("regionNm", "")))
        ]

    result = {
        "year_month": year_month,
        "region_filter": region,
        "count": len(rows),
        "data": rows,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
