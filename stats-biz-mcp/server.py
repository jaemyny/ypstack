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


def _kosis_key() -> str:
    key = os.environ.get("KOSIS_API_KEY", "")
    if not key:
        raise ValueError("KOSIS_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


# 한국부동산원(orgId=408) 상업용부동산 임대동향조사 통계표 ID 매핑
_REB_COMMERCIAL_TBL = {
    # alias              : (TBL_ID, 설명)
    "오피스_임대료":        ("DT_40801_N120301_06", "상권별 오피스 임대료(3층 이상)"),
    "오피스_임대가격지수":  ("DT_40801_N1201_06",   "상권별 오피스 임대가격지수"),
    "오피스_공실률":        ("DT_40801_N12020_06",  "상권별 오피스 공실률"),
    "오피스_수익률":        ("DT_40801_N1301_06",   "상권별 오피스 투자수익률"),
    "오피스_순영업소득":    ("DT_40801_N1303_06",   "상권별 오피스 순영업소득"),
    "오피스_전환율":        ("DT_40801_N1205_06",   "상권별 오피스 전환율"),
    "중대형_임대료":        ("DT_40801_N220302_06", "상권별 중대형 상가 임대료"),
    "중대형_임대가격지수":  ("DT_40801_N2201_06",   "상권별 중대형 상가 임대가격지수"),
    "중대형_공실률":        ("DT_40801_N220201_06", "상권별 중대형 상가 공실률"),
    "중대형_수익률":        ("DT_40801_N2301_06",   "상권별 중대형 상가 투자수익률"),
    "소규모_임대료":        ("DT_40801_N420302_06", "상권별 소규모 상가 임대료"),
    "소규모_임대가격지수":  ("DT_40801_N4201_06",   "상권별 소규모 상가 임대가격지수"),
    "소규모_공실률":        ("DT_40801_N420201_06", "상권별 소규모 상가 공실률"),
    "소규모_수익률":        ("DT_40801_N4301_06",   "상권별 소규모 상가 투자수익률"),
    "집합_임대료":          ("DT_40801_N3203_06",   "상권별 집합 상가 임대료"),
    "집합_임대가격지수":    ("DT_40801_N3201_06",   "상권별 집합 상가 임대가격지수"),
    "집합_공실률":          ("DT_40801_N320201_06", "상권별 집합 상가 공실률"),
    "집합_수익률":          ("DT_40801_N3301_06",   "상권별 집합 상가 투자수익률"),
}


# 서울 25개 자치구명 → 행정구역 코드 매핑 (시군구 5자리 코드 = "11" + 자치구 3자리)
SEOUL_DISTRICT_CODE = {
    "종로구": "11110", "중구":   "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구":"11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구":"11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구":"11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}


def _resolve_district_code(district: Optional[str], code: Optional[str] = None) -> Optional[str]:
    """자치구 이름 또는 코드를 받아 5자리 시군구 코드로 정규화."""
    if code:
        return str(code)
    if not district:
        return None
    d = district.strip()
    # 이미 코드인 경우
    if d.isdigit():
        return d
    # 부분일치 (예: "강남" → "강남구")
    for name, c in SEOUL_DISTRICT_CODE.items():
        if d == name or d in name or name.replace("구", "") == d:
            return c
    return None


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
    date: Union[str, int],
    area_code: Optional[Union[str, int]] = None,
    district: Optional[str] = None,
) -> str:
    """
    서울시 자치구별 일별 유동인구 조회 (서울 열린데이터광장).

    Args:
        date: 조회일 YYYYMMDD (예: "20240101")
        area_code: 자치구 코드 필터 (예: "11680" = 강남구). 미입력 시 전체 자치구
        district: 자치구 이름으로 필터 (예: "강남구", "마포구"). area_code의 친화 alias

    Returns:
        JSON 문자열 — {date, area_filter, count, data:[{STDR_DE, SIGNGU_CD, SIGNGU_NM, TOT_LVPOP_CO}]}
    """
    date = str(date)
    # district 이름이 들어오면 코드로 변환 (area_code가 비어있을 때만)
    if not area_code and district:
        resolved = _resolve_district_code(district)
        if resolved:
            area_code = resolved
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
    quarter: Union[str, int],
    stat_type: str = "중대형_임대가격지수",
    region: Optional[str] = None,
    limit: Optional[int] = 30,
) -> str:
    """
    한국부동산원 상업용부동산 임대동향조사 (KOSIS orgId=408 백엔드).
    분기별 데이터를 반환합니다.

    Args:
        quarter: 분기 — YYYYMM 형식 ("202504" = 2025년 4분기)
                 또는 YYYY (해당 연도 4분기 자동) 또는 YYYYQ (예: "2025Q1" → "202501")
        stat_type: 통계 유형 alias. 다음 중 하나 (기본: "중대형_임대가격지수"):
            오피스_임대료, 오피스_임대가격지수, 오피스_공실률, 오피스_수익률,
            중대형_임대료, 중대형_임대가격지수, 중대형_공실률, 중대형_수익률,
            소규모_임대료, 소규모_임대가격지수, 소규모_공실률, 소규모_수익률,
            집합_임대료, 집합_임대가격지수, 집합_공실률, 집합_수익률
            ※ 임대료=원/m2, 임대가격지수=2024.4=100, 공실률=%, 수익률=%
        region: 상권/시도 부분일치 필터 (예: "서울", "강남", "전국"). 미입력 시 전체
        limit: 최대 반환 건수 (기본 30)

    Returns:
        JSON — {quarter, stat_type, tbl_id, region_filter, count, data:[{period, region, item, value, unit}]}
    """
    try:
        key = _kosis_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    if stat_type not in _REB_COMMERCIAL_TBL:
        return json.dumps({
            "error": f"지원하지 않는 stat_type: {stat_type}",
            "supported": list(_REB_COMMERCIAL_TBL.keys()),
        }, ensure_ascii=False, indent=2)

    # quarter 정규화: YYYY → YYYY04, YYYYQn → YYYY0n, YYYYMM 그대로
    q = str(quarter).strip().upper().replace("Q", "")
    if len(q) == 4:        # YYYY → 4분기
        q = q + "04"
    elif len(q) == 5:      # YYYYQ (Q 제거 후 5자리) → 0 패딩
        q = q[:4] + "0" + q[4]

    tbl_id, tbl_name = _REB_COMMERCIAL_TBL[stat_type]

    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": key,
        "orgId": "408",
        "tblId": tbl_id,
        "itmId": "ALL",
        "objL1": "ALL",
        "prdSe": "Q",
        "startPrdDe": q,
        "endPrdDe": q,
        "format": "json",
        "jsonVD": "Y",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    if isinstance(data, dict) and data.get("err"):
        return json.dumps({
            "error": f"KOSIS 오류 {data.get('err')}: {data.get('errMsg', '')}",
            "tbl_id": tbl_id,
            "quarter": q,
            "hint": "분기 형식이 잘못됐을 수 있습니다. 예: '202504'(=2025년 4분기), '2025'(=2025년 4분기), '2025Q1'",
        }, ensure_ascii=False, indent=2)

    rows = data if isinstance(data, list) else []

    # region 부분일치 필터
    if region:
        rows = [r for r in rows if region in r.get("C1_NM", "")]

    parsed = [
        {
            "period":  r.get("PRD_DE", ""),
            "region":  r.get("C1_NM", ""),
            "item":    r.get("ITM_NM", ""),
            "value":   r.get("DT", ""),
            "unit":    r.get("UNIT_NM", ""),
        }
        for r in rows[: (limit or 30)]
    ]

    return json.dumps(
        {
            "quarter": q,
            "stat_type": stat_type,
            "tbl_name": tbl_name,
            "tbl_id": tbl_id,
            "region_filter": region,
            "count": len(parsed),
            "matched_total": len(rows),
            "data": parsed,
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
