"""
stats-finance-mcp: 한국은행 ECOS + OpenDART 금융 데이터 MCP 서버
"""
import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stats-finance")

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _ecos_key() -> str:
    key = os.environ.get("ECOS_API_KEY", "")
    if not key:
        raise ValueError("ECOS_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _dart_key() -> str:
    key = os.environ.get("DART_API_KEY", "")
    if not key:
        raise ValueError("DART_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


ECOS_BASE = "https://ecos.bok.or.kr/api"
DART_BASE = "https://opendart.fss.or.kr/api"

# 주기별 날짜 포맷 변환
def _ecos_date(d: str, cycle: str = "M") -> str:
    """ECOS 날짜 포맷 변환. 일별(D)은 YYYYMMDD, 월별(M)/기타는 YYYYMM 그대로."""
    if cycle == "D" and len(d) == 6:
        return d + "01"
    return d

# stat_code별 아이템코드+기본주기 매핑
ECOS_ITEM_MAP = {
    "722Y001": ("0101000", "M"),   # 기준금리 (월별 집계 가능)
    "817Y002": ("0000000", "D"),   # CD금리 (일별)
    "121Y006": ("BECBLA01", "M"),  # 예금은행 대출금리(신규)
    "731Y003": ("5000000", "D"),   # 국고채 3년 (일별)
    "731Y005": ("5020000", "D"),   # 국고채 10년 (일별)
}


async def _get(url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# 도구 1: ecos_search_stats
# ---------------------------------------------------------------------------

@mcp.tool()
async def ecos_search_stats(keyword: str, limit: Optional[int] = 20) -> str:
    """
    한국은행 ECOS 통계 테이블 검색.

    Args:
        keyword: 검색어 (예: '기준금리', 'CPI', '환율')
        limit: 최대 반환 건수 (기본 20)

    Returns:
        JSON 문자열 — {keyword, count, items:[{stat_code, stat_name, cycle, start_time, end_time}]}
    """
    try:
        key = _ecos_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    url = f"{ECOS_BASE}/StatisticTableList/{key}/json/kr/1/{limit}/{keyword}"
    try:
        data = await _get(url)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    root = data.get("StatisticTableList", {})
    rows = root.get("row", [])
    if isinstance(rows, dict):
        rows = [rows]

    items = [
        {
            "stat_code": r.get("STAT_CODE", ""),
            "stat_name": r.get("STAT_NAME", ""),
            "cycle": r.get("CYCLE", ""),
            "start_time": r.get("START_TIME", ""),
            "end_time": r.get("END_TIME", ""),
        }
        for r in rows
    ]

    result = {
        "keyword": keyword,
        "count": root.get("list_total_count", len(items)),
        "items": items,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 2: ecos_get_interest_rate
# ---------------------------------------------------------------------------

@mcp.tool()
async def ecos_get_interest_rate(
    start_date: str,
    end_date: str,
    stat_code: Optional[str] = "722Y001",
    cycle: Optional[str] = None,
) -> str:
    """
    한국은행 ECOS 금리 데이터 조회.

    주요 stat_code:
      722Y001 = 기준금리 (기본값, 월별)
      817Y002 = CD금리 (91일, 일별)
      121Y006 = COFIX (신규취급액기준, 월별)
      731Y003 = 국고채 3년 (일별)
      731Y005 = 국고채 10년 (일별)

    Args:
        start_date: 시작일 YYYYMM (예: "202301")
        end_date: 종료일 YYYYMM (예: "202412")
        stat_code: 통계코드 (기본 722Y001 = 기준금리)
        cycle: 주기 D/M/Q/Y (미입력 시 stat_code 기본값 사용)

    Returns:
        JSON 문자열 — {stat_code, period, count, data:[{date, stat_name, item_name, value, unit}]}
    """
    try:
        key = _ecos_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    item_code, default_cycle = ECOS_ITEM_MAP.get(stat_code, ("", "M"))
    use_cycle = cycle or default_cycle
    s = _ecos_date(start_date, use_cycle)
    e = _ecos_date(end_date, use_cycle)
    item_suffix = f"/{item_code}" if item_code else ""
    url = (
        f"{ECOS_BASE}/StatisticSearch/{key}/json/kr/1/120"
        f"/{stat_code}/{use_cycle}/{s}/{e}{item_suffix}"
    )
    try:
        data = await _get(url)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    rows = data.get("StatisticSearch", {}).get("row", [])
    if isinstance(rows, dict):
        rows = [rows]

    records = [
        {
            "date": r.get("TIME", ""),
            "stat_name": r.get("STAT_NAME", ""),
            "item_name": r.get("ITEM_NAME1", ""),
            "value": r.get("DATA_VALUE", ""),
            "unit": r.get("UNIT_NAME", ""),
        }
        for r in rows
    ]

    result = {
        "stat_code": stat_code,
        "period": f"{start_date} ~ {end_date}",
        "count": len(records),
        "data": records,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 3: ecos_get_economic_indicator
# ---------------------------------------------------------------------------

INDICATOR_MAP = {
    # (stat_code, ecos_cycle, item_code)  — ecos_cycle: M/D/Q/A
    "CPI":    ("901Y009", "M", ""),    # 소비자물가지수 총지수 (월별)
    "환율":   ("731Y001", "D", ""),    # 주요국 대원화환율 (일별, 원달러 포함)
    "실업률": ("901Y027", "M", ""),    # 경제활동인구조사 (월별, 실업률/취업자 등 포함)
    "GDP":    ("200Y001", "Q", ""),    # GDP 분기 (날짜 형식: YYYYMM01~YYYYMM31)
    "통화량": ("101Y002", "M", "BBHS00"), # M2 광의통화 계절조정 (월별)
}


@mcp.tool()
async def ecos_get_economic_indicator(
    indicator: str,
    start_date: str,
    end_date: str,
    cycle: Optional[str] = None,
) -> str:
    """
    한국 주요 경제지표 조회.

    Args:
        indicator: 지표명 — "CPI" | "환율" | "실업률" | "GDP" | "통화량"
        start_date: 시작일 (YYYYMM, 환율은 YYYYMMDD)
        end_date: 종료일 (YYYYMM, 환율은 YYYYMMDD)
        cycle: ECOS 주기 M/D/Q/A. 미입력 시 지표별 기본값 사용

    Returns:
        JSON 문자열 — {indicator, stat_code, period, count, data:[{date, value, unit}]}
    """
    try:
        key = _ecos_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    if indicator not in INDICATOR_MAP:
        return json.dumps(
            {
                "error": f"지원하지 않는 지표입니다: {indicator}",
                "supported": list(INDICATOR_MAP.keys()),
            },
            ensure_ascii=False,
        )

    stat_code, default_cycle, item_code = INDICATOR_MAP[indicator]
    use_cycle = cycle or default_cycle

    # 주기별 날짜 포맷 변환
    def _fmt(d: str, cyc: str) -> str:
        if cyc == "A" and len(d) >= 4:
            return d[:4]           # YYYYMM → YYYY (연간)
        if cyc == "D" and len(d) == 6:
            return d + "01"        # YYYYMM → YYYYMMDD (일별)
        return d

    s = _fmt(start_date, use_cycle)
    e = _fmt(end_date, use_cycle)
    item_suffix = f"/{item_code}" if item_code else ""

    url = (
        f"{ECOS_BASE}/StatisticSearch/{key}/json/kr/1/200"
        f"/{stat_code}/{use_cycle}/{s}/{e}{item_suffix}"
    )
    try:
        data = await _get(url)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    rows = data.get("StatisticSearch", {}).get("row", [])
    if isinstance(rows, dict):
        rows = [rows]

    records = [
        {
            "date": r.get("TIME", ""),
            "stat_name": r.get("STAT_NAME", ""),
            "item_name": r.get("ITEM_NAME1", ""),
            "value": r.get("DATA_VALUE", ""),
            "unit": r.get("UNIT_NAME", ""),
        }
        for r in rows
    ]

    result = {
        "indicator": indicator,
        "stat_code": stat_code,
        "cycle": use_cycle,
        "period": f"{start_date} ~ {end_date}",
        "count": len(records),
        "data": records,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 4: ecos_get_housing_loan_rate
# ---------------------------------------------------------------------------

@mcp.tool()
async def ecos_get_housing_loan_rate(start_date: str, end_date: str) -> str:
    """
    주택담보대출 관련 금리 비교 조회 (COFIX + 기준금리).

    Args:
        start_date: 시작일 YYYYMM
        end_date: 종료일 YYYYMM

    Returns:
        JSON 문자열 — {period, series:[{stat_code, name, data:[{date, value, unit}]}]}
    """
    try:
        key = _ecos_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    targets = [
        ("121Y006", "COFIX (신규취급액기준)"),
        ("722Y001", "한국은행 기준금리"),
    ]

    series = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for stat_code, label in targets:
            item_code, default_cycle = ECOS_ITEM_MAP.get(stat_code, ("", "M"))
            use_cycle = default_cycle
            s = _ecos_date(start_date, use_cycle)
            e = _ecos_date(end_date, use_cycle)
            item_suffix = f"/{item_code}" if item_code else ""
            url = (
                f"{ECOS_BASE}/StatisticSearch/{key}/json/kr/1/120"
                f"/{stat_code}/{use_cycle}/{s}/{e}{item_suffix}"
            )
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                series.append({"stat_code": stat_code, "name": label, "error": str(e)})
                continue

            rows = data.get("StatisticSearch", {}).get("row", [])
            if isinstance(rows, dict):
                rows = [rows]

            records = [
                {
                    "date": r.get("TIME", ""),
                    "value": r.get("DATA_VALUE", ""),
                    "unit": r.get("UNIT_NAME", ""),
                }
                for r in rows
            ]
            series.append({"stat_code": stat_code, "name": label, "data": records})

    result = {"period": f"{start_date} ~ {end_date}", "series": series}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 5: dart_search_company
# ---------------------------------------------------------------------------

@mcp.tool()
async def dart_search_company(corp_name: str, limit: Optional[int] = 10) -> str:
    """
    OpenDART 기업 검색.

    Args:
        corp_name: 검색할 기업명 (부분 일치 가능)
        limit: 최대 반환 건수 (기본 10)

    Returns:
        JSON 문자열 — {count, companies:[{corp_code, corp_name, stock_code, modify_date}]}
    """
    try:
        key = _dart_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # corpCode.xml(ZIP) 다운로드 → 기업명 부분일치 검색
    import io, zipfile, xml.etree.ElementTree as ET
    zip_url = f"{DART_BASE}/corpCode.xml?crtfc_key={key}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(zip_url)
            resp.raise_for_status()
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            xml_data = zf.read(zf.namelist()[0])
            root = ET.fromstring(xml_data)
    except Exception as e:
        return json.dumps({"error": f"DART corpCode 다운로드 실패: {e}"}, ensure_ascii=False)

    companies = []
    for item in root.findall("list"):
        name = item.findtext("corp_name", "")
        if corp_name.lower() not in name.lower():
            continue
        stock_code = item.findtext("stock_code", "").strip()
        companies.append({
            "corp_code": item.findtext("corp_code", ""),
            "corp_name": name,
            "stock_code": stock_code if stock_code else "-",
            "modify_date": item.findtext("modify_date", ""),
        })
        if len(companies) >= limit:
            break

    result = {"count": len(companies), "companies": companies}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 6: dart_get_disclosure_list
# ---------------------------------------------------------------------------

@mcp.tool()
async def dart_get_disclosure_list(
    corp_code: str,
    start_date: str,
    end_date: str,
    limit: Optional[int] = 20,
) -> str:
    """
    OpenDART 공시 목록 조회.

    Args:
        corp_code: 8자리 기업코드 (dart_search_company 결과에서 확인)
        start_date: 시작일 YYYYMMDD
        end_date: 종료일 YYYYMMDD
        limit: 최대 반환 건수 (기본 20)

    Returns:
        JSON 문자열 — {corp_code, count, disclosures:[{report_nm, rcept_dt, flr_nm, rcept_no}]}
    """
    try:
        key = _dart_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    url = f"{DART_BASE}/list.json"
    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bgn_de": start_date,
        "end_de": end_date,
        "pblntf_ty": "A",
        "page_count": limit,
    }
    try:
        data = await _get(url, params)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    status = data.get("status", "")
    if status != "000":
        return json.dumps(
            {"error": data.get("message", f"DART 오류 코드: {status}")},
            ensure_ascii=False,
        )

    rows = data.get("list", [])
    disclosures = [
        {
            "report_nm": r.get("report_nm", ""),
            "rcept_dt": r.get("rcept_dt", ""),
            "flr_nm": r.get("flr_nm", ""),
            "rcept_no": r.get("rcept_no", ""),
        }
        for r in rows
    ]

    result = {
        "corp_code": corp_code,
        "count": data.get("total_count", len(disclosures)),
        "disclosures": disclosures,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 7: dart_get_financial_statement
# ---------------------------------------------------------------------------

REPORT_TYPE_MAP = {
    "11011": "사업보고서",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서",
}


@mcp.tool()
async def dart_get_financial_statement(
    corp_code: str,
    year: str,
    report_type: Optional[str] = "11011",
) -> str:
    """
    OpenDART 단일 기업 재무제표 조회 (연결재무제표 우선).

    Args:
        corp_code: 8자리 기업코드
        year: 사업연도 YYYY
        report_type: 보고서 종류
          11011 = 사업보고서 (기본값)
          11012 = 반기보고서
          11013 = 1분기보고서
          11014 = 3분기보고서

    Returns:
        JSON 문자열 — {corp_code, year, report_type, count, financials:[{account_nm, current_amount, previous_amount}]}
    """
    try:
        key = _dart_key()
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    url = f"{DART_BASE}/fnlttSinglAcnt.json"
    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": report_type,
        "fs_div": "CFS",
    }
    try:
        data = await _get(url, params)
    except Exception as e:
        return json.dumps({"error": f"API 호출 실패: {e}"}, ensure_ascii=False)

    status = data.get("status", "")
    if status != "000":
        return json.dumps(
            {"error": data.get("message", f"DART 오류 코드: {status}")},
            ensure_ascii=False,
        )

    rows = data.get("list", [])
    financials = [
        {
            "account_nm": r.get("account_nm", ""),
            "current_amount": r.get("thstrm_amount", ""),
            "previous_amount": r.get("frmtrm_amount", ""),
        }
        for r in rows
    ]

    result = {
        "corp_code": corp_code,
        "year": year,
        "report_type": REPORT_TYPE_MAP.get(report_type, report_type),
        "count": len(financials),
        "financials": financials,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
