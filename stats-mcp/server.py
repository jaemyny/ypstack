"""
stats-mcp: 한국 인구/가구 통계 MCP 서버
- KOSIS (인구, 가구 통계)
- SGIS (지역별 인구통계)
- 서울시 열린데이터광장 (생활인구)
- 경기데이터드림 안내
"""

import json
import os
import time
from typing import Optional, Union

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

# ── MCP 앱 초기화 ─────────────────────────────────────────────
mcp = FastMCP("stats-mcp")

# ── 환경변수 ──────────────────────────────────────────────────
KOSIS_API_KEY = os.getenv("KOSIS_API_KEY", "")
SGIS_CONSUMER_KEY = os.getenv("SGIS_CONSUMER_KEY", "")
SGIS_CONSUMER_SECRET = os.getenv("SGIS_CONSUMER_SECRET", "")
SEOUL_API_KEY = os.getenv("SEOUL_API_KEY", "")
GG_API_KEY = os.getenv("GG_API_KEY", "")

# ── 도구 공통 annotations ─────────────────────────────────────
_ANNOT = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

# ── SGIS 토큰 캐시 ────────────────────────────────────────────
_sgis_token: str | None = None
_sgis_token_time: float = 0.0


async def _get_sgis_token() -> str:
    global _sgis_token, _sgis_token_time
    # 토큰 유효기간 23시간
    if _sgis_token and (time.time() - _sgis_token_time) < 82800:
        return _sgis_token
    url = "https://sgis.kostat.go.kr/OpenAPI2/service/rest/Authentication/authServiceKey"
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(url, params={
            "consumer_key": SGIS_CONSUMER_KEY,
            "consumer_secret": SGIS_CONSUMER_SECRET,
        })
        data = r.json()
        if data.get("errCode") != 0:
            raise ValueError(f"SGIS 인증 실패: {data.get('errMsg')}")
        _sgis_token = data["result"]["accessToken"]
        _sgis_token_time = time.time()
        return _sgis_token


# ── Pydantic 입력 모델 ────────────────────────────────────────

class KosisSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str
    limit: Optional[int] = 20


class KosisGetDataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    org_id: str
    tbl_id: str
    obj_l1: Optional[str] = "ALL"
    obj_l2: Optional[str] = "ALL"
    itm_id: Optional[str] = "ALL"
    prd_se: Optional[str] = "Y"
    start_period: Optional[str] = None
    end_period: Optional[str] = None
    limit: Optional[int] = 100


class KosisRegionYearInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    region: Optional[str] = None
    year: Optional[str] = None


class KosisHouseholdDetailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    region_code: str
    age_code: Optional[str] = None
    itm_id: Optional[str] = None
    year: Optional[str] = "2024"


class SgisRegionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    area_id: str
    division: Optional[int] = 2
    year: Optional[str] = "2024"


class SeoulLivingPopInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    date: str
    district_code: Optional[str] = None


class GgSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str
    limit: Optional[int] = 10


# ── 공통 헬퍼 ─────────────────────────────────────────────────

def _check_kosis_key() -> Optional[str]:
    if not KOSIS_API_KEY:
        return "KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    return None


def _filter_by_region(items: list, region: Optional[str]) -> list:
    """region 부분일치 필터. 정확 매칭(시도명) 우선, 없으면 부분일치 fallback."""
    if not region:
        return items
    region_norm = region.strip()
    # 1) 정확 매칭 또는 표준 시도명 매칭 (예: "대구" → "대구광역시")
    sido_aliases = {
        "서울": ("서울특별시",),
        "부산": ("부산광역시",), "대구": ("대구광역시",), "인천": ("인천광역시",),
        "광주": ("광주광역시",), "대전": ("대전광역시",), "울산": ("울산광역시",),
        "세종": ("세종특별자치시",),
        "경기": ("경기도",), "강원": ("강원특별자치도", "강원도"),
        "충북": ("충청북도",), "충남": ("충청남도",),
        "전북": ("전북특별자치도", "전라북도"), "전남": ("전라남도",),
        "경북": ("경상북도",), "경남": ("경상남도",), "제주": ("제주특별자치도",),
    }
    candidates = sido_aliases.get(region_norm, ())
    exact_match = [
        it for it in items
        if it.get("C1_NM", "") == region_norm
        or it.get("C1_NM", "") in candidates
    ]
    if exact_match:
        return exact_match
    # 2) Fallback: 부분일치
    return [
        it for it in items
        if region_norm in it.get("C1_NM", "") or region_norm in it.get("C1_NM_ENG", "")
    ]


def _parse_kosis_row(row: dict) -> dict:
    return {
        "period": row.get("PRD_DE", ""),
        "c1_code": row.get("C1", ""),
        "c1_name": row.get("C1_NM", ""),
        "c2_code": row.get("C2", ""),
        "c2_name": row.get("C2_NM", ""),
        "itm_id": row.get("ITM_ID", ""),
        "itm_name": row.get("ITM_NM", ""),
        "value": row.get("DT", ""),
        "unit": row.get("UNIT_NM", ""),
    }


# ── 도구 1: kosis_search_stats ────────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_search_stats(keyword: str, limit: int = 20) -> str:
    """
    KOSIS에서 통계표를 키워드로 검색합니다.

    Args:
        keyword: 검색 키워드 (예: "인구", "가구", "출생")
        limit: 최대 결과 수 (기본 20)
    """
    err = _check_kosis_key()
    if err:
        return err

    url = "https://kosis.kr/openapi/statisticsSearch.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_API_KEY,
        "vwCd": "MT_ZTITLE",
        "parentListId": "",
        "searchNm": keyword,
        "format": "json",
        "jsonVD": "Y",
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        data = r.json()

    if isinstance(data, dict) and data.get("err"):
        return f"KOSIS 오류: {data.get('errMsg', data)}"

    items = data if isinstance(data, list) else []
    items = items[:limit]

    results = []
    for it in items:
        results.append({
            "org_id": it.get("ORG_ID", ""),
            "tbl_id": it.get("TBL_ID", ""),
            "tbl_name": it.get("TBL_NM", ""),
            "org_name": it.get("ORG_NM", ""),
            "period": f"{it.get('STRT_PRD_DE', '')}~{it.get('END_PRD_DE', '')}",
        })

    return json.dumps(
        {"keyword": keyword, "count": len(results), "results": results},
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 2: kosis_get_data ────────────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_data(
    org_id: str,
    tbl_id: str,
    obj_l1: str = "ALL",
    obj_l2: str = "ALL",
    itm_id: str = "ALL",
    prd_se: str = "Y",
    start_period: Optional[str] = None,
    end_period: Optional[str] = None,
    limit: int = 100,
) -> str:
    """
    KOSIS 통계표에서 데이터를 조회합니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 통계표 ID (예: "DT_1B040A3")
        obj_l1: 분류1 코드 (기본 "ALL")
        obj_l2: 분류2 코드 (기본 "ALL")
        itm_id: 항목 ID (기본 "ALL")
        prd_se: 수록 주기 (Y=연, M=월, Q=분기, 기본 "Y")
        start_period: 시작 기간 (예: "2020", "202001")
        end_period: 종료 기간 (예: "2024", "202412")
        limit: 최대 결과 수 (기본 100)
    """
    err = _check_kosis_key()
    if err:
        return err

    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_API_KEY,
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": itm_id,
        "objL1": obj_l1,
        "objL2": obj_l2,
        "prdSe": prd_se,
        "startPrdDe": start_period or "",
        "endPrdDe": end_period or "",
        "format": "json",
        "jsonVD": "Y",
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        data = r.json()

    if isinstance(data, dict):
        err_code = data.get("err")
        if err_code == 31:
            return (
                "조회 결과가 40,000셀을 초과했습니다. "
                "obj_l1 또는 obj_l2에 특정 코드를 지정하여 범위를 좁혀 주세요. "
                f"(orgId={org_id}, tblId={tbl_id})"
            )
        if err_code:
            return f"KOSIS 오류 {err_code}: {data.get('errMsg', data)}"

    rows = data if isinstance(data, list) else []
    rows = rows[:limit]
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {"orgId": org_id, "tblId": tbl_id, "count": len(parsed), "data": parsed},
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 3: kosis_get_population ──────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_population(
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
) -> str:
    """
    KOSIS에서 시도별 주민등록인구 통계를 조회합니다 (tblId=DT_1B040A3).

    Args:
        region: 지역명 필터 (예: "서울", "경기", None=전체)
        year: 연도 필터 (예: "2023", None=전체)
    """
    year = str(year) if year is not None else None
    err = _check_kosis_key()
    if err:
        return err

    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_API_KEY,
        "orgId": "101",
        "tblId": "DT_1B040A3",
        "itmId": "T20",
        "objL1": "ALL",
        "objL2": "",
        "prdSe": "Y",
        "startPrdDe": year or "",
        "endPrdDe": year or "",
        "format": "json",
        "jsonVD": "Y",
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        data = r.json()

    if isinstance(data, dict) and data.get("err"):
        return f"KOSIS 오류: {data.get('errMsg', data)}"

    rows = data if isinstance(data, list) else []
    rows = _filter_by_region(rows, region)
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {"type": "주민등록인구", "region": region, "year": year, "count": len(parsed), "data": parsed},
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 4: kosis_get_household ───────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_household(
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
) -> str:
    """
    KOSIS에서 시도별 가구 통계를 조회합니다 (tblId=DT_1B040B3).

    Args:
        region: 지역명 필터 (예: "서울", "부산", None=전체)
        year: 연도 필터 (예: "2023", None=전체)
    """
    year = str(year) if year is not None else None
    err = _check_kosis_key()
    if err:
        return err

    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_API_KEY,
        "orgId": "101",
        "tblId": "DT_1B040B3",
        "itmId": "ALL",
        "objL1": "ALL",
        "objL2": "",
        "prdSe": "Y",
        "startPrdDe": year or "",
        "endPrdDe": year or "",
        "format": "json",
        "jsonVD": "Y",
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        data = r.json()

    if isinstance(data, dict) and data.get("err"):
        return f"KOSIS 오류: {data.get('errMsg', data)}"

    rows = data if isinstance(data, list) else []
    rows = _filter_by_region(rows, region)
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {"type": "가구통계", "region": region, "year": year, "count": len(parsed), "data": parsed},
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 5: kosis_get_household_detail ───────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_household_detail(
    region_code: str,
    age_code: Optional[str] = None,
    itm_id: Optional[str] = None,
    year: Optional[Union[str, int]] = "2024",
) -> str:
    """
    KOSIS 가구주 연령×가구원수 교차 통계를 조회합니다 (tblId=DT_1JC1511).
    이 테이블은 시도(2자리) 단위만 지원합니다.
    5자리 이상 시군구 코드는 자동으로 앞 2자리로 변환됩니다.

    Args:
        region_code: 시도 코드 2자리 (예: "11"=서울, "26"=부산, "41"=경기)
        age_code: 연령 코드 (예: "035"=30~34세, "040"=35~39세, "000"=합계, None=ALL)
        itm_id: 항목 ID (예: "T100"=일반가구, None=ALL). 합계 비교 시 "T100" 권장.
        year: 기준 연도 (기본 "2024")
    """
    year = str(year) if year is not None else "2024"
    err = _check_kosis_key()
    if err:
        return err

    # 시군구 코드(5자리) → 시도 코드(2자리) 자동 변환
    auto_trim_note = None
    if region_code and len(region_code) > 2:
        original = region_code
        region_code = region_code[:2]
        auto_trim_note = f"region_code '{original}' → '{region_code}' 자동 변환됨 (이 테이블은 시도 단위만 지원)"

    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_API_KEY,
        "orgId": "101",
        "tblId": "DT_1JC1511",
        "itmId": itm_id or "ALL",
        "objL1": region_code,
        "objL2": age_code or "ALL",
        "prdSe": "Y",
        "startPrdDe": year or "",
        "endPrdDe": year or "",
        "format": "json",
        "jsonVD": "Y",
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        data = r.json()

    if isinstance(data, dict):
        err_code = data.get("err")
        if err_code == 31:
            return (
                "조회 결과가 40,000셀을 초과했습니다. "
                "age_code 또는 itm_id를 구체적으로 지정하여 범위를 좁혀 주세요. "
                "예시) age_code='000'(합계), itm_id='T100'(전체가구)"
            )
        if err_code:
            return f"KOSIS 오류 {err_code}: {data.get('errMsg', data)}"

    rows = data if isinstance(data, list) else []
    parsed = [_parse_kosis_row(r) for r in rows]

    result = {
        "type": "가구주연령×가구원수 (DT_1JC1511, 시도단위)",
        "region_code": region_code,
        "age_code": age_code,
        "itm_id": itm_id,
        "year": year,
        "count": len(parsed),
        "data": parsed,
    }
    if auto_trim_note:
        result["note"] = auto_trim_note
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── 도구 6: sgis_get_region_stats ─────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def sgis_get_region_stats(
    area_id: str,
    division: int = 2,
    year: Optional[Union[str, int]] = "2024",
) -> str:
    """
    SGIS(통계지리정보서비스)에서 지역별 인구통계를 조회합니다.

    Args:
        area_id: 지역 코드 (예: "11"=서울특별시, "11230"=강남구, "11710"=송파구)
        division: 행정구역 단위 (1=시도, 2=시군구, 3=읍면동, 기본 2)
        year: 기준 연도 (기본 "2024")
    """
    year = str(year) if year is not None else "2024"
    return json.dumps({
        "error": (
            "SGIS OpenAPI v2 (sgis.kostat.go.kr/OpenAPI2)가 서비스 종료되었습니다. "
            "v3 endpoint(sgis.kostat.go.kr/OpenAPI3)로 이전되었으나 인증 절차가 변경되어 "
            "현재 자동 호출이 불가합니다."
        ),
        "alternative": [
            "kosis_get_population(region, year) — 시도별 인구통계",
            "seoul_get_living_population(date, district_code) — 서울 생활인구",
            "sgis_get_region_stats 대체 데이터를 SGIS 웹사이트(sgis.kostat.go.kr)에서 직접 확인",
        ],
        "area_id": area_id,
        "division": division,
        "year": year,
    }, ensure_ascii=False, indent=2)


# ── 도구 7: seoul_get_living_population ───────────────────────

@mcp.tool(annotations=_ANNOT)
async def seoul_get_living_population(
    date: str,
    district_code: Optional[str] = None,
) -> str:
    """
    서울시 열린데이터광장에서 생활인구(추정 체류인구) 데이터를 조회합니다.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식, 예: "20240101")
        district_code: 집계구 코드 (선택, 미입력 시 전체)
    """
    if not SEOUL_API_KEY:
        return "SEOUL_API_KEY 환경변수가 설정되지 않았습니다."

    base_url = f"http://openapi.seoul.go.kr:8088/{SEOUL_API_KEY}/json/SPOP_DAILYSUM_JACHI/1/100/{date}/"
    if district_code:
        base_url += f"{district_code}/"

    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(base_url)
        data = r.json()

    service_data = data.get("SPOP_DAILYSUM_JACHI", {})
    if service_data.get("RESULT", {}).get("CODE") != "INFO-000":
        msg = service_data.get("RESULT", {}).get("MESSAGE", str(data))
        return f"서울 열린데이터 오류: {msg}"

    rows = service_data.get("row", [])

    return json.dumps(
        {
            "type": "서울 생활인구",
            "date": date,
            "district_code": district_code,
            "count": len(rows),
            "data": rows,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 8: gg_search_stats ───────────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def gg_search_stats(keyword: str, limit: int = 10) -> str:
    """
    경기데이터드림 통계 서비스 안내 및 URL 예시를 반환합니다.
    경기데이터드림은 개별 서비스명이 필요하므로, 키워드에 맞는 주요 서비스를 안내합니다.

    Args:
        keyword: 검색 키워드 (예: "인구", "사업체", "복지", "교통")
        limit: 반환할 서비스 안내 수 (기본 10)
    """
    if not GG_API_KEY:
        return "GG_API_KEY 환경변수가 설정되지 않았습니다."

    SERVICE_MAP = {
        "인구": [
            ("ForeigRsdntPoptn", "외국인주민 인구현황"),
            ("RegPoptn", "주민등록 인구통계"),
        ],
        "사업체": [
            ("ReggltnLctnMst", "등록사업체 위치기준 현황"),
            ("IndutyBizplcCo", "산업별 사업체수"),
        ],
        "복지": [
            ("WlfFclt", "복지시설 현황"),
            ("WlfBnftCo", "복지급여 수급자수"),
        ],
        "교통": [
            ("RoadAccdnt", "교통사고 현황"),
            ("BusPsngr", "버스 승객수"),
        ],
        "주택": [
            ("HouseHoldCo", "가구수 현황"),
            ("AptTrd", "아파트 거래 현황"),
        ],
        "고용": [
            ("EmplymntInsrncPicr", "고용보험 피보험자수"),
            ("JbsekrRgstn", "구직자 등록 현황"),
        ],
    }

    matched = []
    kw_lower = keyword.lower()
    for category, services in SERVICE_MAP.items():
        if category in keyword or kw_lower in category.lower():
            matched.extend(services)

    if not matched:
        # 전체 주요 서비스 반환
        for services in SERVICE_MAP.values():
            matched.extend(services)

    matched = matched[:limit]

    examples = []
    for svc_id, svc_name in matched:
        examples.append({
            "service_id": svc_id,
            "service_name": svc_name,
            "example_url": (
                f"https://openapi.gg.go.kr/{svc_id}"
                f"?KEY={GG_API_KEY}&Type=json&pIndex=1&pSize=100"
            ),
        })

    return json.dumps(
        {
            "keyword": keyword,
            "message": (
                "경기데이터드림은 개별 서비스명이 필요합니다. "
                "아래 서비스 ID와 URL 예시를 참고하여 직접 조회하세요."
            ),
            "services": examples,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 진입점 ────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
