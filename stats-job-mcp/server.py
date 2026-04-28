"""
stats-job-mcp: 한국 고용/소득/사업체 통계 MCP 서버
- KOSIS (취업자, 임금, 사업체 통계)
- 국민연금공단 data.go.kr (사업장/가입자 현황)
"""

import json
import os
import xml.etree.ElementTree as ET
from typing import Optional, Union

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

# ── MCP 앱 초기화 ─────────────────────────────────────────────
mcp = FastMCP("stats-job")

# ── 환경변수 ──────────────────────────────────────────────────
KOSIS_API_KEY = os.getenv("KOSIS_API_KEY", "")
DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_KEY", "")

# ── 도구 공통 annotations ─────────────────────────────────────
_ANNOT = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


# ── Pydantic 입력 모델 ────────────────────────────────────────

class KosisRegionYearInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    region: Optional[str] = None
    year: Optional[str] = None


class KosisJobSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str
    limit: Optional[int] = 10


class NpsSubscriberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sido_cd: Optional[str] = None
    sigungu_cd: Optional[str] = None


# ── 공통 헬퍼 ─────────────────────────────────────────────────

def _check_kosis_key() -> Optional[str]:
    if not KOSIS_API_KEY:
        return "KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    return None


def _filter_by_region(items: list, region: Optional[str]) -> list:
    if not region:
        return items
    return [
        it for it in items
        if region in it.get("C1_NM", "") or region in it.get("C1_NM_ENG", "")
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


async def _kosis_fetch(
    org_id: str,
    tbl_id: str,
    itm_id: str = "ALL",
    obj_l1: str = "ALL",
    obj_l2: str = "",
    prd_se: str = "Y",
    year: Optional[str] = None,
) -> list:
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
            raise ValueError(
                "조회 결과가 40,000셀을 초과했습니다. "
                "조회 범위(지역, 연도 등)를 좁혀 주세요."
            )
        if err_code:
            raise ValueError(f"KOSIS 오류 {err_code}: {data.get('errMsg', data)}")

    return data if isinstance(data, list) else []


# ── 도구 1: kosis_get_employment_stats ───────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_employment_stats(
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
) -> str:
    """
    KOSIS에서 시도별 취업자수·실업률 등 고용통계를 조회합니다 (tblId=DT_1DA7002S).

    Args:
        region: 지역명 필터 (예: "서울", "경기", None=전체)
        year: 연도 필터 (예: "2023", None=전체)
    """
    year = str(year) if year is not None else None
    err = _check_kosis_key()
    if err:
        return err

    try:
        rows = await _kosis_fetch(
            org_id="101",
            tbl_id="DT_1DA7002S",
            itm_id="ALL",
            obj_l1="ALL",
            prd_se="Y",
            year=year,
        )
    except ValueError as e:
        return str(e)

    rows = _filter_by_region(rows, region)
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {
            "type": "지역별 고용통계 (취업자·실업률)",
            "region": region,
            "year": year,
            "count": len(parsed),
            "data": parsed,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 2: kosis_get_wage_stats ──────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_wage_stats(
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
) -> str:
    """
    KOSIS에서 지역별·산업별 월평균임금 통계를 조회합니다 (tblId=DT_LB_EW).

    Args:
        region: 지역명 필터 (예: "서울", "부산", None=전체)
        year: 연도 필터 (예: "2023", None=전체)
    """
    year = str(year) if year is not None else None
    err = _check_kosis_key()
    if err:
        return err

    try:
        rows = await _kosis_fetch(
            org_id="350",
            tbl_id="DT_LB_EW",
            itm_id="ALL",
            obj_l1="ALL",
            prd_se="Y",
            year=year,
        )
    except ValueError as e:
        return str(e)

    rows = _filter_by_region(rows, region)
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {
            "type": "지역별 월평균임금",
            "region": region,
            "year": year,
            "count": len(parsed),
            "data": parsed,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 3: kosis_get_business_count ─────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_get_business_count(
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
) -> str:
    """
    KOSIS 전국사업체조사에서 지역별 사업체수·종사자수를 조회합니다 (tblId=DT_1BC01).

    Args:
        region: 지역명 필터 (예: "서울", "경기", None=전체)
        year: 연도 필터 (예: "2022", None=전체)
    """
    year = str(year) if year is not None else None
    err = _check_kosis_key()
    if err:
        return err

    try:
        rows = await _kosis_fetch(
            org_id="101",
            tbl_id="DT_1BC01",
            itm_id="ALL",
            obj_l1="ALL",
            prd_se="Y",
            year=year,
        )
    except ValueError as e:
        return str(e)

    rows = _filter_by_region(rows, region)
    parsed = [_parse_kosis_row(r) for r in rows]

    return json.dumps(
        {
            "type": "전국사업체조사 (사업체수·종사자수)",
            "region": region,
            "year": year,
            "count": len(parsed),
            "data": parsed,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 4: kosis_search_job_stats ────────────────────────────

@mcp.tool(annotations=_ANNOT)
async def kosis_search_job_stats(
    keyword: str,
    limit: int = 10,
) -> str:
    """
    KOSIS에서 고용·소득·사업체 관련 통계표를 키워드로 검색합니다.

    Args:
        keyword: 검색 키워드 (예: "취업자", "임금", "사업체", "고용", "실업률")
        limit: 최대 결과 수 (기본 10)
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
        {
            "keyword": keyword,
            "hint": "org_id와 tbl_id를 kosis_get_data 도구에 사용하면 상세 데이터를 조회할 수 있습니다.",
            "count": len(results),
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 도구 5: nps_get_subscriber_stats ─────────────────────────

@mcp.tool(annotations=_ANNOT)
async def nps_get_subscriber_stats(
    sido_cd: Optional[Union[str, int]] = None,
    sigungu_cd: Optional[Union[str, int]] = None,
) -> str:
    """
    국민연금공단 API에서 지역별 사업장수·가입자수를 조회합니다.

    Args:
        sido_cd: 시도 코드 (예: "11"=서울, "41"=경기, "26"=부산, None=전체)
        sigungu_cd: 시군구 코드 (예: "680"=강남구, None=전체)
    """
    sido_cd = str(sido_cd) if sido_cd is not None else None
    sigungu_cd = str(sigungu_cd) if sigungu_cd is not None else None
    if not DATA_GO_KR_KEY:
        return "DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."

    url = "http://apis.data.go.kr/B490003/NpsTblView/getBizPlaceCount"
    params: dict = {
        "serviceKey": DATA_GO_KR_KEY,
        "pageNo": 1,
        "numOfRows": 100,
    }
    if sido_cd:
        params["siDoCd"] = sido_cd
    if sigungu_cd:
        params["siGunGuCd"] = sigungu_cd

    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        raw = r.text

    # XML 파싱
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return f"XML 파싱 오류: {e}\n응답 원문: {raw[:500]}"

    result_code = root.findtext(".//resultCode", "")
    result_msg = root.findtext(".//resultMsg", "")

    if result_code not in ("00", "000", "0000"):
        return f"국민연금 API 오류 [{result_code}]: {result_msg}"

    total_count = root.findtext(".//totalCount", "0")
    items = root.findall(".//item")
    parsed = []
    for item in items:
        row = {child.tag: child.text for child in item}
        parsed.append(row)

    return json.dumps(
        {
            "type": "국민연금 지역별 사업장·가입자 현황",
            "sido_cd": sido_cd,
            "sigungu_cd": sigungu_cd,
            "total_count": total_count,
            "returned": len(parsed),
            "data": parsed,
        },
        ensure_ascii=False,
        indent=2,
    )


# ── 진입점 ────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
