#!/usr/bin/env python3
"""
stats-realty-mcp: 한국 부동산 실거래가 · 가격지수 · 공급 · 단지 정보
- 국토부 RTMS: 아파트 매매/전월세/분양권전매 실거래가
- 한국부동산원 R-ONE: 가격지수, 전세가율
- 국토부: 공동주택 단지 목록/기본정보, 주택 인허가, 공동주택공시가격
- KB부동산: 가격지수·HAI·PIR (PublicDataReader, 무키)
"""
import json, os, re, xml.etree.ElementTree as ET
from typing import Optional, Union
import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stats-realty")

DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_KEY", "")
REB_API_KEY    = os.getenv("REB_API_KEY", "")
KOSIS_API_KEY  = os.getenv("KOSIS_API_KEY", "")

# 서울 25개 자치구 시군구 코드 매핑 (LLM이 "강남구"로 호출 시 자동 변환)
SEOUL_SIGUNGU_CODE = {
    "종로구": "11110", "중구":   "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구":"11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구":"11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구":"11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}

# 시도명 → KOSIS C1_NM 정규화 (별칭 → 표준 명)
SIDO_ALIASES = {
    "서울": "서울특별시",  "부산": "부산광역시",  "대구": "대구광역시",
    "인천": "인천광역시",  "광주": "광주광역시",  "대전": "대전광역시",
    "울산": "울산광역시",  "세종": "세종특별자치시",
    "경기": "경기도",      "강원": "강원특별자치도", "강원도": "강원특별자치도",
    "충북": "충청북도",    "충남": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전남": "전라남도",
    "경북": "경상북도",    "경남": "경상남도",  "제주": "제주특별자치도",
}


def _resolve_sigungu(district: Optional[str], code: Optional[str] = None) -> Optional[str]:
    """자치구 이름 또는 코드를 시군구 5자리 코드로 정규화."""
    if code:
        return str(code).strip()
    if not district:
        return None
    d = str(district).strip()
    if d.isdigit():
        return d
    for name, c in SEOUL_SIGUNGU_CODE.items():
        if d == name or d == name.replace("구", "") or d in name:
            return c
    return None


def _resolve_sido(name: Optional[str]) -> Optional[str]:
    """시도명을 KOSIS 표준 시도명으로 정규화."""
    if not name:
        return None
    n = str(name).strip()
    return SIDO_ALIASES.get(n, n)


RTMS_TRADE_URL    = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RTMS_RENT_URL     = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
RTMS_PRESALE_URL  = "http://apis.data.go.kr/1613000/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade"
APT_LIST_URL      = "http://apis.data.go.kr/1613000/AptListService2/getRhLtncAptList"
APT_DETAIL_URL    = "http://apis.data.go.kr/1613000/AptBasisInfoService1/getAphusBassInfo"
HOUSING_PMT_URL   = "http://apis.data.go.kr/1613000/HousePermitInfoService/getHousePermitInfo"
REB_BASE          = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
KOSIS_BASE        = "https://kosis.kr/openapi"

# ---------------------------------------------------------------------------
# KB부동산 PublicDataReader 옵션 임포트
# ---------------------------------------------------------------------------
try:
    from PublicDataReader import Kbland
    import pandas as pd
    HAS_KBLAND = True
except ImportError:
    HAS_KBLAND = False

# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

async def _get_xml(url: str, params: dict) -> ET.Element:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return ET.fromstring(r.text)


async def _get_json(url: str, params: dict) -> dict | list:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _txt(el: ET.Element, tag: str) -> str:
    e = el.find(tag)
    return e.text.strip() if e is not None and e.text else ""


def _err(e: Exception, context: str = "") -> str:
    """에러를 사용자에게 전달할 수 있는 형태로 직렬화."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        body = (e.response.text or "").strip()[:200]
        if status == 500:
            return json.dumps({
                "error": f"공공데이터포털(data.go.kr) 서버 오류 (HTTP 500){': ' + context if context else ''}",
                "raw": body or "Unexpected errors",
                "hint": "잠시 후 재시도하거나, 일시적인 정부 API 점검 가능성을 확인해주세요.",
            }, ensure_ascii=False, indent=2)
        return json.dumps({
            "error": f"HTTP {status} 오류{': ' + context if context else ''}",
            "raw": body,
        }, ensure_ascii=False, indent=2)
    if isinstance(e, httpx.TimeoutException):
        return json.dumps({"error": "요청 시간 초과(30s)"}, ensure_ascii=False, indent=2)
    return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 법정동코드 내장 매핑
# ---------------------------------------------------------------------------

LAWD_CD_MAP = {
    "서울": "11", "서울종로구": "11110", "서울중구": "11140",
    "서울용산구": "11170", "서울성동구": "11200", "서울광진구": "11215",
    "서울동대문구": "11230", "서울중랑구": "11260", "서울성북구": "11290",
    "서울강북구": "11305", "서울도봉구": "11320", "서울노원구": "11350",
    "서울은평구": "11380", "서울서대문구": "11410", "서울마포구": "11440",
    "서울양천구": "11470", "서울강서구": "11500", "서울구로구": "11530",
    "서울금천구": "11545", "서울영등포구": "11560", "서울동작구": "11590",
    "서울관악구": "11620", "서울서초구": "11650", "서울강남구": "11680",
    "서울송파구": "11710", "서울강동구": "11740",
    "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41",
    "경기성남시분당구": "41135", "경기수원시": "41110",
    "경기용인시수지구": "41465", "경기화성시": "41590",
    "경기과천시": "41290", "경기하남시": "41450",
}

# ---------------------------------------------------------------------------
# 도구 1: 아파트 매매 실거래가
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def rtms_get_apt_trade(
    lawd_cd: str,
    deal_ymd: str,
    apt_name: Optional[str] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    limit: Optional[int] = 50,
) -> str:
    """국토부 RTMS 아파트 매매 실거래가를 조회합니다.

    Args:
        lawd_cd: 법정동코드 앞 5자리 (예: "11680" = 서울 강남구)
        deal_ymd: 거래년월 (YYYYMM, 예: "202403")
        apt_name: 아파트명 필터 (선택)
        min_area: 최소 전용면적(㎡) 필터 (선택)
        max_area: 최대 전용면적(㎡) 필터 (선택)
        limit: 최대 반환 건수 (기본 50)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    try:
        root = await _get_xml(RTMS_TRADE_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1",
        })
        items = root.findall(".//item")
        result = []
        for item in items:
            name = _txt(item, "aptNm")
            area_str = _txt(item, "excluUseAr")
            try:
                area = float(area_str)
            except ValueError:
                area = 0.0
            price_str = _txt(item, "dealAmount").replace(",", "").strip()
            try:
                price = int(price_str)
            except ValueError:
                price = 0

            if apt_name and apt_name not in name:
                continue
            if min_area is not None and area < min_area:
                continue
            if max_area is not None and area > max_area:
                continue

            result.append({
                "apt_name": name,
                "area_m2": area,
                "area_pyeong": round(area / 3.305785, 1),
                "floor": _txt(item, "floor"),
                "price_만원": price,
                "date": f"{_txt(item, 'dealYear')}-{_txt(item, 'dealMonth').zfill(2)}-{_txt(item, 'dealDay').zfill(2)}",
                "build_year": _txt(item, "buildYear"),
                "dong": _txt(item, "umdNm"),
            })

        result.sort(key=lambda x: x["price_만원"], reverse=True)
        result = result[:limit]

        return json.dumps({
            "lawd_cd": lawd_cd,
            "deal_ymd": deal_ymd,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 2: 아파트 전월세 실거래가
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def rtms_get_apt_rent(
    lawd_cd: str,
    deal_ymd: str,
    apt_name: Optional[str] = None,
    limit: Optional[int] = 50,
) -> str:
    """국토부 RTMS 아파트 전월세 실거래가를 조회합니다.

    Args:
        lawd_cd: 법정동코드 앞 5자리 (예: "11680" = 서울 강남구)
        deal_ymd: 거래년월 (YYYYMM, 예: "202403")
        apt_name: 아파트명 필터 (선택)
        limit: 최대 반환 건수 (기본 50)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    try:
        root = await _get_xml(RTMS_RENT_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1",
        })
        items = root.findall(".//item")
        result = []
        for item in items:
            name = _txt(item, "aptNm")
            if apt_name and apt_name not in name:
                continue
            monthly = _txt(item, "monthlyRent").replace(",", "").strip()
            rent_type = "월세" if monthly not in ("", "0") else "전세"
            try:
                area = float(_txt(item, "excluUseAr"))
            except ValueError:
                area = 0.0
            result.append({
                "apt_name": name,
                "area_m2": area,
                "area_pyeong": round(area / 3.305785, 1),
                "floor": _txt(item, "floor"),
                "deposit_만원": _txt(item, "deposit").replace(",", "").strip(),
                "monthly_만원": monthly,
                "rent_type": rent_type,
                "date": f"{_txt(item, 'dealYear')}-{_txt(item, 'dealMonth').zfill(2)}-{_txt(item, 'dealDay').zfill(2)}",
                "dong": _txt(item, "umdNm"),
            })

        result = result[:limit]
        return json.dumps({
            "lawd_cd": lawd_cd,
            "deal_ymd": deal_ymd,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 3: 분양권전매 실거래가
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def rtms_get_apt_presale_transfer(
    lawd_cd: str,
    deal_ymd: str,
    limit: Optional[int] = 50,
) -> str:
    """국토부 RTMS 분양권전매 실거래가를 조회합니다.

    Args:
        lawd_cd: 법정동코드 앞 5자리 (예: "11680" = 서울 강남구)
        deal_ymd: 거래년월 (YYYYMM, 예: "202403")
        limit: 최대 반환 건수 (기본 50)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    try:
        root = await _get_xml(RTMS_PRESALE_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1",
        })
        items = root.findall(".//item")
        result = []
        for item in items:
            price_str = _txt(item, "dealAmount").replace(",", "").strip()
            try:
                price = int(price_str)
            except ValueError:
                price = 0
            try:
                area = float(_txt(item, "excluUseAr"))
            except ValueError:
                area = 0.0
            result.append({
                "apt_name": _txt(item, "aptNm"),
                "area_m2": area,
                "area_pyeong": round(area / 3.305785, 1),
                "floor": _txt(item, "floor"),
                "price_만원": price,
                "date": f"{_txt(item, 'dealYear')}-{_txt(item, 'dealMonth').zfill(2)}-{_txt(item, 'dealDay').zfill(2)}",
                "dong": _txt(item, "umdNm"),
            })

        result.sort(key=lambda x: x["price_만원"], reverse=True)
        result = result[:limit]
        return json.dumps({
            "lawd_cd": lawd_cd,
            "deal_ymd": deal_ymd,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 4: 공동주택 단지 검색
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def apt_search_complex(
    sigungu_cd: Optional[str] = None,
    apt_name: Optional[str] = None,
    district: Optional[str] = None,
    limit: Optional[int] = 20,
) -> str:
    """공동주택 단지 목록을 조회합니다.

    Args:
        sigungu_cd: 시군구코드 5자리 (예: "11680" = 강남구). district로 대체 가능.
        apt_name: 아파트명 필터 (선택, 부분일치)
        district: 자치구 이름 (예: "강남구", "마포구"). sigungu_cd의 친화 alias.
                  ※ 시군구 단위 검색만 지원 — 전국 검색은 정부 API 자체가 미지원입니다.
        limit: 최대 반환 건수 (기본 20)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    # district 이름 → 코드 자동 변환 (sigungu_cd 미지정 시)
    resolved = _resolve_sigungu(district, sigungu_cd)
    if not resolved:
        return json.dumps({
            "error": "sigungu_cd 또는 district가 필요합니다.",
            "hint": "정부 API는 시군구 단위로만 검색을 지원합니다. 예: sigungu_cd='11680' 또는 district='강남구'",
            "supported_districts": list(SEOUL_SIGUNGU_CODE.keys()),
        }, ensure_ascii=False, indent=2)
    sigungu_cd = resolved
    try:
        root = await _get_xml(APT_LIST_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "numOfRows": "100",
            "pageNo": "1",
            "sggCd": sigungu_cd,
        })
        items = root.findall(".//item")
        result = []
        for item in items:
            name = _txt(item, "kaptName")
            if apt_name and apt_name not in name:
                continue
            result.append({
                "kaptCode": _txt(item, "kaptCode"),
                "kaptName": name,
                "kaptAddr": _txt(item, "kaptAddr"),
                "households": _txt(item, "houseHolCnt"),
                "usedate": _txt(item, "kaptUsedate"),
            })

        result = result[:limit]
        return json.dumps({
            "sigungu_cd": sigungu_cd,
            "count": len(result),
            "complexes": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 5: 공동주택 기본정보 상세
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def apt_get_complex_detail(kapt_code: str) -> str:
    """공동주택 단지 기본정보를 조회합니다.

    Args:
        kapt_code: 단지코드 (apt_search_complex로 조회 가능)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    try:
        root = await _get_xml(APT_DETAIL_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "kaptCode": kapt_code,
        })
        item = root.find(".//item")
        if item is None:
            return json.dumps({"error": "단지 정보를 찾을 수 없습니다.", "kapt_code": kapt_code}, ensure_ascii=False, indent=2)

        data = {child.tag: (child.text.strip() if child.text else "") for child in item}
        data["kapt_code"] = kapt_code
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 6: 주택 인허가 실적
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def molit_get_housing_permit(
    sido: Optional[str] = None,
    year_month: Optional[Union[str, int]] = None,
    region: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
    limit: Optional[int] = 50,
) -> str:
    """국토부 주택 인허가 실적을 조회합니다.

    Args:
        sido: 시도명 (예: "서울특별시", "경기도"). region으로 대체 가능.
        year_month: 조회 기간 (YYYYMM 예: "202403", 또는 YYYY 예: "2024" → 해당 연도 전체).
                    year로 대체 가능.
        region: sido의 친화 alias (예: "서울"=서울특별시 자동 변환)
        year: year_month의 친화 alias (4자리 YYYY)
        limit: 최대 반환 건수 (기본 50)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    # alias 정규화
    sido = _resolve_sido(sido or region)
    ym = year_month if year_month is not None else year
    if ym is None:
        return json.dumps({
            "error": "year_month(또는 year)가 필요합니다.",
            "examples": ["year_month='202403' (특정월)", "year='2024' (연도 전체)"],
        }, ensure_ascii=False, indent=2)
    if not sido:
        return json.dumps({
            "error": "sido(또는 region)가 필요합니다.",
            "examples": ["sido='서울특별시'", "region='경기'(=경기도)"],
        }, ensure_ascii=False, indent=2)
    try:
        ym = str(ym).strip()
        # 4자리 연도인 경우 해당 연도 전체로 처리
        if len(ym) == 4:
            start_ymd = ym + "01"
            end_ymd = ym + "12"
        else:
            start_ymd = ym
            end_ymd = ym

        root = await _get_xml(HOUSING_PMT_URL, {
            "serviceKey": DATA_GO_KR_KEY,
            "numOfRows": "100",
            "pageNo": "1",
            "startYmd": start_ymd,
            "endYmd": end_ymd,
        })
        items = root.findall(".//item")
        result = []
        for item in items:
            sggnm = _txt(item, "sggnm") or _txt(item, "sigunguNm") or _txt(item, "sidoNm")
            if sido and sido not in (sggnm or ""):
                continue
            result.append({
                "sggnm": sggnm,
                "year": _txt(item, "bldgYear") or _txt(item, "year"),
                "month": _txt(item, "bldgMon") or _txt(item, "month"),
                "house_type": _txt(item, "houseType") or _txt(item, "hsType"),
                "permit_cnt": _txt(item, "permitCnt") or _txt(item, "permiCnt"),
                "start_cnt": _txt(item, "startCnt"),
                "complete_cnt": _txt(item, "completeCnt"),
            })

        result = result[:limit]
        return json.dumps({
            "sido": sido,
            "period": year_month,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 7: 한국부동산원 아파트 가격지수 — 주간 (KOSIS orgId=408)
# ---------------------------------------------------------------------------

# 주간 아파트 가격지수 테이블 (A/B 버전 동일 데이터, B가 최신)
_REB_TBL = {
    "매매":       ("408", "DT_304004_WEEK_002_B"),  # 주간 아파트 매매가격지수
    "전세":       ("408", "DT_304004_WEEK_004_A"),  # 주간 아파트 전세가격지수
    "매매변동률":  ("408", "DT_304004_WEEK_001_B"),  # 주간 아파트 매매가격지수 변동률
    "전세변동률":  ("408", "DT_304004_WEEK_003_B"),  # 주간 아파트 전세가격지수 변동률
}

# 월간 주택/아파트 가격지수 테이블 (KOSIS orgId=101, 시도/시/군/구 단위)
_REB_MONTHLY_TBL = {
    "아파트매매":     ("101", "DT_1YL20162E"),   # 아파트 매매가격지수
    "아파트전세":     ("101", "DT_1YL20172E"),   # 아파트 전세가격지수
    "아파트월세통합": ("101", "DT_1YL20182E"),   # 아파트 월세통합가격지수
    "아파트월세":     ("101", "DT_1YL20192E"),   # 아파트 월세가격지수
    "주택매매":       ("101", "DT_1YL13502E"),   # 주택(종합) 매매가격지수
    "주택전세":       ("101", "DT_1YL13602E"),   # 주택(종합) 전세가격지수
    "주택월세통합":   ("101", "DT_1YL20142E"),   # 주택(종합) 월세통합가격지수
    "주택월세":       ("101", "DT_1YL20152E"),   # 주택(종합) 월세가격지수
}

# 주택 매매 거래 현황 테이블 (KOSIS orgId=408)
_REB_TRADE_TBL = {
    "행정구역별":    ("408", "DT_408_2006_S0057"),  # 행정구역별 주택매매거래현황
    "주택유형별":    ("408", "DT_408_2006_S0061"),  # 주택유형별 주택매매거래현황
    "매입자거주지별": ("408", "DT_408_2006_S0058"), # 매입자거주지별 주택매매거래현황
    "거래주체별":    ("408", "DT_408_2006_S0059"),  # 거래주체별 주택매매거래현황
    "거래규모별":    ("408", "DT_408_2006_S0060"),  # 거래규모별 주택매매거래현황
    "매입자연령대별": ("408", "DT_408_2006_S0076"), # 매입자연령대별 주택매매거래현황
}

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def reb_get_price_index(
    year_month: Optional[Union[str, int]] = None,
    stat_type: str = "매매",
    region: Optional[str] = None,
    price_type: Optional[str] = None,
    region_code: Optional[str] = None,
) -> str:
    """한국부동산원 주간 아파트 가격지수를 조회합니다. (KOSIS orgId=408)

    주간 단위 아파트 가격지수/변동률을 제공합니다.
    월간 시도·구 단위 지수가 필요하면 reb_get_monthly_price_index를 사용하세요.

    Args:
        year_month: 조회년월 (YYYYMM, 예: "202503") — 해당 월의 주간 데이터를 반환
        stat_type: 통계 유형 — "매매" | "전세" | "매매변동률" | "전세변동률" (기본 "매매")
        region: 지역명 필터 (선택, 예: "서울", "수도권", "전국")
        price_type: stat_type 친화 alias (예: "매매" / "전세")
        region_code: (호환용 — 시도 코드. KOSIS C1_NM과 매칭되지 않으므로 region 사용 권장)
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    # alias 처리
    if price_type and not stat_type:
        stat_type = price_type
    elif price_type:
        stat_type = price_type  # price_type 우선
    if year_month is None:
        return json.dumps({
            "error": "year_month가 필요합니다 (YYYYMM, 예: '202503')",
        }, ensure_ascii=False, indent=2)
    year_month = str(year_month).strip()
    # region_code가 들어오면 시도명으로 변환 시도 (sido 코드 → 표준명)
    if region_code and not region:
        sido_code_map = {
            "11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시",
            "24": "광주광역시", "25": "대전광역시", "26": "울산광역시", "29": "세종특별자치시",
            "31": "경기도", "32": "강원특별자치도", "33": "충청북도", "34": "충청남도",
            "35": "전북특별자치도", "36": "전라남도", "37": "경상북도", "38": "경상남도",
            "39": "제주특별자치도",
        }
        rc = str(region_code).strip()[:2]
        region = sido_code_map.get(rc)
    # KOSIS REB 주간지수 표는 C1_NM이 "서울", "수도권" 등 단축형을 사용하므로
    # _resolve_sido 적용 없이 원본 입력값으로 부분일치 필터링한다.

    if stat_type not in _REB_TBL:
        return json.dumps(
            {"error": f"지원하지 않는 stat_type: {stat_type}. ('매매' 또는 '전세')"},
            ensure_ascii=False, indent=2,
        )
    org_id, tbl_id = _REB_TBL[stat_type]
    # YYYYMM → 주간 범위: YYYYMM01 ~ YYYYMM31
    start_w = year_month + "01"
    end_w   = year_month + "31"
    try:
        url = f"{KOSIS_BASE}/Param/statisticsParameterData.do"
        params = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": org_id,
            "tblId": tbl_id,
            "itmId": "ALL",
            "objL1": "ALL",
            "prdSe": "W",
            "startPrdDe": start_w,
            "endPrdDe": end_w,
            "format": "json",
            "jsonVD": "Y",
        }
        data = await _get_json(url, params)
        if isinstance(data, dict) and data.get("err"):
            return json.dumps(
                {"error": f"KOSIS 오류 {data['err']}: {data.get('errMsg', '')}"},
                ensure_ascii=False, indent=2,
            )

        rows = data if isinstance(data, list) else []
        if region:
            rows = [r for r in rows if region in r.get("C1_NM", "") or r.get("C1_NM", "") in region]

        result_rows = [
            {
                "region": r.get("C1_NM", ""),
                "week": r.get("PRD_DE", ""),
                "index": r.get("DT", ""),
                "unit": r.get("UNIT_NM", ""),
                "item": r.get("ITM_NM", ""),
            }
            for r in rows
        ]
        return json.dumps({
            "stat_type": stat_type,
            "year_month": year_month,
            "source": f"KOSIS 한국부동산원 ({tbl_id})",
            "count": len(result_rows),
            "data": result_rows,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 7-B: 한국부동산원 월간 부동산 가격지수 (KOSIS orgId=101, 시도/시/군/구)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def reb_get_monthly_price_index(
    stat_type: str = "아파트매매",
    start_ym: Optional[Union[str, int]] = None,
    end_ym: Optional[Union[str, int]] = None,
    region: Optional[str] = None,
    housing_type: Optional[str] = None,
) -> str:
    """한국부동산원 월간 부동산 가격지수를 시도·시·군·구 단위로 조회합니다. (KOSIS orgId=101)

    아파트·주택 전체의 매매·전세·월세 가격지수를 제공합니다.
    주간 지수가 필요하면 reb_get_price_index를 사용하세요.

    Args:
        stat_type: 통계 유형.
            아파트: "아파트매매" | "아파트전세" | "아파트월세통합" | "아파트월세"
            주택전체: "주택매매" | "주택전세" | "주택월세통합" | "주택월세"
        start_ym: 시작 연월 (YYYYMM, 예: "202501"). 없으면 end_ym 기준 단일 월
        end_ym: 종료 연월 (YYYYMM, 예: "202503"). 필수
        region: 지역 필터 (예: "서울", "서울특별시", "강남구"). 없으면 전국 전체 반환
        housing_type: 주택유형 필터 — "아파트", "단독주택", "연립다세대", "종합". 없으면 전체
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    if stat_type not in _REB_MONTHLY_TBL:
        return json.dumps({
            "error": f"지원하지 않는 stat_type: '{stat_type}'",
            "valid": list(_REB_MONTHLY_TBL.keys()),
        }, ensure_ascii=False, indent=2)
    if end_ym is None and start_ym is None:
        return json.dumps({
            "error": "start_ym 또는 end_ym이 필요합니다 (YYYYMM, 예: '202503')",
        }, ensure_ascii=False, indent=2)

    org_id, tbl_id = _REB_MONTHLY_TBL[stat_type]
    s_ym = str(start_ym).strip() if start_ym else str(end_ym).strip()
    e_ym = str(end_ym).strip() if end_ym else s_ym

    try:
        url = f"{KOSIS_BASE}/Param/statisticsParameterData.do"
        params = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": org_id,
            "tblId": tbl_id,
            "itmId": "ALL",
            "objL1": "ALL",
            "objL2": "ALL",
            "prdSe": "M",
            "startPrdDe": s_ym,
            "endPrdDe": e_ym,
            "format": "json",
            "jsonVD": "Y",
        }
        data = await _get_json(url, params)
        if isinstance(data, dict) and data.get("err"):
            return json.dumps(
                {"error": f"KOSIS 오류 {data['err']}: {data.get('errMsg', '')}"},
                ensure_ascii=False, indent=2,
            )

        rows = data if isinstance(data, list) else []
        if region:
            rows = [r for r in rows if region in r.get("C1_NM", "") or r.get("C1_NM", "") in region]
        if housing_type:
            rows = [r for r in rows if housing_type in r.get("C2_NM", "")]

        result_rows = [
            {
                "region": r.get("C1_NM", ""),
                "housing_type": r.get("C2_NM", ""),
                "period": r.get("PRD_DE", ""),
                "index": r.get("DT", ""),
                "unit": r.get("UNIT_NM", ""),
                "item": r.get("ITM_NM", ""),
            }
            for r in rows
        ]
        return json.dumps({
            "stat_type": stat_type,
            "period": f"{s_ym}~{e_ym}",
            "source": f"KOSIS 한국부동산원 ({tbl_id})",
            "region_filter": region,
            "housing_type_filter": housing_type,
            "count": len(result_rows),
            "data": result_rows,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 7-C: 한국부동산원 주택 매매 거래 현황 (KOSIS orgId=408)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def reb_get_housing_trade(
    trade_type: str = "행정구역별",
    year_month: Optional[Union[str, int]] = None,
    region: Optional[str] = None,
) -> str:
    """한국부동산원 주택 매매 거래 현황을 조회합니다. (KOSIS orgId=408)

    지역·유형·연령·거주지별 주택 매매 거래 건수를 제공합니다.

    Args:
        trade_type: 조회 유형.
            "행정구역별" | "주택유형별" | "매입자거주지별" | "거래주체별" | "거래규모별" | "매입자연령대별"
        year_month: 조회 연월 (YYYYMM, 예: "202503"). 없으면 최근 전체 데이터
        region: 지역 필터 (예: "서울", "경기"). 없으면 전국
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    if trade_type not in _REB_TRADE_TBL:
        return json.dumps({
            "error": f"지원하지 않는 trade_type: '{trade_type}'",
            "valid": list(_REB_TRADE_TBL.keys()),
        }, ensure_ascii=False, indent=2)

    org_id, tbl_id = _REB_TRADE_TBL[trade_type]

    try:
        url = f"{KOSIS_BASE}/Param/statisticsParameterData.do"
        params = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": org_id,
            "tblId": tbl_id,
            "itmId": "ALL",
            "objL1": "ALL",
            "prdSe": "M",
            "format": "json",
            "jsonVD": "Y",
        }
        if year_month:
            ym = str(year_month).strip()
            params["startPrdDe"] = ym
            params["endPrdDe"] = ym

        data = await _get_json(url, params)
        if isinstance(data, dict) and data.get("err"):
            return json.dumps(
                {"error": f"KOSIS 오류 {data['err']}: {data.get('errMsg', '')}"},
                ensure_ascii=False, indent=2,
            )

        rows = data if isinstance(data, list) else []
        if region:
            rows = [r for r in rows if region in r.get("C1_NM", "") or r.get("C1_NM", "") in region]

        result_rows = [
            {
                "region": r.get("C1_NM", ""),
                "category": r.get("C2_NM", ""),
                "period": r.get("PRD_DE", ""),
                "count": r.get("DT", ""),
                "unit": r.get("UNIT_NM", ""),
                "item": r.get("ITM_NM", ""),
            }
            for r in rows
        ]
        return json.dumps({
            "trade_type": trade_type,
            "source": f"KOSIS 한국부동산원 ({tbl_id})",
            "region_filter": region,
            "year_month": str(year_month) if year_month else None,
            "count": len(result_rows),
            "data": result_rows,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 8: KB부동산 통계 (PublicDataReader)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_price_stats(
    stat_type: str = "매매지수",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """[DEPRECATED] KB부동산 가격통계 통합 도구.

    ⚠️ 이 도구는 deprecated 되었습니다. 다음 개별 도구를 사용하세요:
      • stat_type="매매지수"/"전세지수" → KB 서버측 거부로 사용 불가.
        대안: kb_get_price_index_change_rate / kb_get_lead50 / kb_get_average_price
      • stat_type="HAI"  → kb_get_hai 직접 호출 권장
      • stat_type="PIR"  → kb_get_pir 직접 호출 권장
    """
    return json.dumps(
        {
            "error": "kb_get_price_stats는 deprecated 되었습니다.",
            "deprecated": True,
            "redirect_map": {
                "매매지수": "kb_get_price_index_change_rate / kb_get_lead50 / kb_get_average_price",
                "전세지수": "kb_get_price_index_change_rate(deal_type='전세') / kb_get_average_price(deal_type='전세')",
                "HAI":      "kb_get_hai",
                "PIR":      "kb_get_pir",
            },
            "requested": {
                "stat_type": stat_type,
                "region_code": region_code,
                "period": period,
            },
        },
        ensure_ascii=False, indent=2,
    )


# ---------------------------------------------------------------------------
# KB부동산 공통 상수 · 헬퍼
# ---------------------------------------------------------------------------

_KB_CYCLE_CODE    = {"monthly": "01", "weekly": "02"}
_KB_PROPERTY_CODE = {"APT": "01", "아파트": "01", "연립": "08", "단독": "09", "종합": "98"}
_KB_DEAL_CODE     = {"매매": "01", "전세": "02"}
_KB_AREA_CODE     = {"구분류": "01", "신분류": "02"}
_KB_MARKET_CODE   = {
    "매수우위": "01", "매매거래활발": "02", "전세수급": "03",
    "전세거래활발": "04", "매매가격전망": "05", "전세가격전망": "06",
}
_KB_QUINTILE_CODE = {"APT평균": "01", "주택종합평균": "02", "APT㎡당": "08"}
_KB_PIR_CODE      = {"PIR": "01", "J-PIR": "02"}

_KB_REGION_HINT = {
    "supported_codes": {
        "11": "서울특별시", "21": "부산광역시", "22": "대구광역시",
        "23": "인천광역시", "24": "광주광역시", "25": "대전광역시",
        "26": "울산광역시", "29": "세종특별자치시",
    },
    "note": "경기(41/42), 강원, 충청, 전라, 경상 등 도단위는 KB API에서 미지원될 수 있습니다.",
}


def _kb_df_to_json(
    df,
    stat_type: str,
    region_code: Optional[str] = None,
    period: Optional[int] = None,
) -> str:
    """KB DataFrame → JSON (None/빈 DF 처리 + 지역·기간 클라이언트 필터)."""
    if df is None:
        return json.dumps(
            {
                "error": f"지역코드 '{region_code}'에 대한 KB 데이터를 불러오지 못했습니다.",
                "hint": (
                    "PublicDataReader의 KB API가 해당 매개변수 조합(주기/매물종별/거래유형/지역)을 "
                    "지원하지 않거나 일시적으로 응답이 비어 있습니다. "
                    "다른 KB 도구(kb_get_average_price, kb_get_median_price, kb_get_market_trend 등)는 "
                    "동일 region_code로 정상 작동할 수 있으니 시도해 보세요."
                ),
                **_KB_REGION_HINT,
                "stat_type": stat_type,
                "region_code": region_code,
            },
            ensure_ascii=False, indent=2,
        )
    if hasattr(df, "empty") and df.empty:
        return json.dumps(
            {"error": "데이터가 없습니다.", "stat_type": stat_type, "region_code": region_code},
            ensure_ascii=False, indent=2,
        )

    # 지역코드 클라이언트 필터 (API가 지역코드를 무시할 경우 대응)
    if region_code:
        rcols = [c for c in df.columns if "지역코드" in c]
        if rcols:
            df = df[df[rcols[0]].astype(str).str.startswith(region_code.zfill(2))].copy()

    # 날짜 기준 기간 필터 (API가 기간 파라미터를 무시할 경우 대응)
    if period:
        dcols = [c for c in df.columns if "날짜" in c or "date" in c.lower() or "ym" in c.lower()]
        if dcols:
            dc = dcols[0]
            df[dc] = pd.to_datetime(df[dc], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=period)
            df = df[df[dc] >= cutoff].copy()
            df[dc] = df[dc].dt.strftime("%Y-%m")

    result = json.loads(df.to_json(orient="records", force_ascii=False))
    return json.dumps(
        {
            "stat_type": stat_type,
            "region_code": region_code,
            "period_months": period,
            "count": len(result),
            "data": result,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# KB 도구 10: 가격지수
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_price_index(
    cycle: str = "monthly",
    property_type: str = "APT",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """[DEPRECATED] KB부동산 주택가격지수.

    ⚠️ KB부동산 서버에서 이 엔드포인트(/data/quick/getPriceIndex)가 거부되어
       현재 데이터를 가져올 수 없습니다 (RemoteDisconnected). 라이브러리 또는
       서버 측 문제이며 코드로 해결 불가합니다.

    **권장 대안 (의미가 다름에 유의):**
      • 시장 동향 파악(상승/하락):  kb_get_price_index_change_rate (가격지수 증감률, 작동 확인)
      • 가격지수 개념의 절대값:     kb_get_lead50 (선도50지수, 작동 확인)
      • 면적별 가격지수 (소/중/대): kb_get_price_index_by_area (작동 확인)
      • 실제 평균가격(원):           kb_get_average_price (작동 확인)

    Args:
        cycle, property_type, deal_type, region_code, period: (호환용 — 실제로는 사용 안 됨)
    """
    return json.dumps(
        {
            "error": "kb_get_price_index는 KB 서버측 엔드포인트 거부로 현재 사용할 수 없습니다.",
            "deprecated": True,
            "alternatives": [
                {"tool": "kb_get_price_index_change_rate", "purpose": "시장 동향(증감률) — 상승/하락 추세 파악"},
                {"tool": "kb_get_lead50",                  "purpose": "선도50지수 — 가격지수 절대값과 가장 유사"},
                {"tool": "kb_get_price_index_by_area",     "purpose": "면적별 가격지수 (소형~대형 5분류)"},
                {"tool": "kb_get_average_price",           "purpose": "실제 평균가격 (원 단위)"},
            ],
            "diagnosis": "PublicDataReader.Kbland().get_price_index() → RemoteDisconnected. KB 서버측 차단 추정.",
            "requested_params": {
                "cycle": cycle, "property_type": property_type, "deal_type": deal_type,
                "region_code": region_code, "period": period,
            },
        },
        ensure_ascii=False, indent=2,
    )


# ---------------------------------------------------------------------------
# KB 도구 11: 가격지수 증감률
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_price_index_change_rate(
    cycle: str = "weekly",
    property_type: str = "APT",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 8,
) -> str:
    """KB부동산 주택가격지수 증감률을 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 주간 1~2

    Args:
        cycle: 주기 ("monthly"=월간, "weekly"=주간, 기본 "weekly")
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11")
        period: 최근 N회차·개월 (기본 8; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    cycle_c = _KB_CYCLE_CODE.get(cycle)
    if not cycle_c:
        return json.dumps({"error": f"지원하지 않는 cycle: {cycle}."}, ensure_ascii=False, indent=2)
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_price_index_change_rate(
            월간주간구분코드=cycle_c,
            매물종별구분=prop_c,
            매매전세코드=deal_c,
            지역코드=region_code,
        )
        return _kb_df_to_json(df, f"가격지수증감률({cycle}/{property_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 12: 면적별 가격지수
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_price_index_by_area(
    cycle: str = "monthly",
    property_type: str = "APT",
    area_type: str = "신분류",
    deal_type: str = "매매",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 전용면적별 주택가격지수를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 31·35(구분류), 39~40(신분류)

    Args:
        cycle: 주기 ("monthly"=월간, "weekly"=주간, 기본 "monthly")
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        area_type: 면적 분류 ("구분류" 또는 "신분류", 기본 "신분류")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        period: 최근 N개월 (기본 12; 기간 파라미터로 API에 직접 전달됨)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    cycle_c = _KB_CYCLE_CODE.get(cycle)
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    area_c = _KB_AREA_CODE.get(area_type)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not cycle_c:
        return json.dumps({"error": f"지원하지 않는 cycle: {cycle}."}, ensure_ascii=False, indent=2)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    if not area_c:
        return json.dumps({"error": f"지원하지 않는 area_type: {area_type}. ('구분류' 또는 '신분류')"}, ensure_ascii=False, indent=2)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_price_index_by_area(
            월간주간구분코드=cycle_c,
            매물종별구분=prop_c,
            면적별코드=area_c,
            매매전세코드=deal_c,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"면적별가격지수({area_type}/{deal_type})", None, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 13: 평균가격
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_average_price(
    property_type: str = "APT",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 평균 매매·전세가를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 41~42

    Args:
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_average_price(
            매물종별구분=prop_c,
            매매전세코드=deal_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"평균가격({property_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 14: 면적별 평균가격
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_average_price_by_area(
    deal_type: str = "매매",
    area_type: str = "신분류",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 전용면적별 평균 매매·전세가를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 32~38 (구분류), 55~58 (신분류)

    Args:
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        area_type: 면적 분류 ("구분류" 또는 "신분류", 기본 "신분류")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    deal_c = _KB_DEAL_CODE.get(deal_type)
    area_c = _KB_AREA_CODE.get(area_type)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    if not area_c:
        return json.dumps({"error": f"지원하지 않는 area_type: {area_type}. ('구분류' 또는 '신분류')"}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_average_price_by_area(
            매매전세코드=deal_c,
            면적별코드=area_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"면적별평균가격({area_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 15: 5분위 평균가격
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_average_price_by_quintile(
    menu_type: str = "APT평균",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 5분위 평균 매매·전세가를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 51~54

    Args:
        menu_type: 메뉴 ("APT평균", "주택종합평균", "APT㎡당", 기본 "APT평균")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    menu_c = _KB_QUINTILE_CODE.get(menu_type)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not menu_c:
        return json.dumps({"error": f"지원하지 않는 menu_type: {menu_type}. ('APT평균','주택종합평균','APT㎡당')"}, ensure_ascii=False, indent=2)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_average_price_by_quintile(
            메뉴코드=menu_c,
            매매전세코드=deal_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"5분위평균가격({menu_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 16: ㎡당 평균가격
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_average_price_per_squaremeter(
    property_type: str = "APT",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 ㎡당 평균 매매·전세가를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 45~50

    Args:
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_average_price_per_squaremeter(
            매물종별구분=prop_c,
            매매전세코드=deal_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"㎡당평균가격({property_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 17: 중위가격
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_median_price(
    property_type: str = "APT",
    deal_type: str = "매매",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 중위 매매·전세가를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 43~44

    Args:
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_median_price(
            매물종별구분=prop_c,
            매매전세코드=deal_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"중위가격({property_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 18: KB 아파트 월세지수
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_wolse_index(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 월간 아파트 월세가격지수를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 9

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_monthly_apartment_wolse_index(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "월세지수", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 19: PIR 및 J-PIR
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_pir(
    pir_type: str = "PIR",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 PIR(소득 대비 주택가격비율) 및 J-PIR을 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 11~12

    Args:
        pir_type: PIR 유형 ("PIR" 또는 "J-PIR", 기본 "PIR")
        region_code: 지역코드 (예: "11"=서울, 기본 "11")
        period: 최근 N개월 (기본 12)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    pir_c = _KB_PIR_CODE.get(pir_type)
    if not pir_c:
        return json.dumps({"error": f"지원하지 않는 pir_type: {pir_type}. ('PIR' 또는 'J-PIR')"}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_pir(
            pir_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"PIR({pir_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 20: KB 아파트 주택담보대출 PIR
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_mortgage_loan_pir(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 아파트 주택담보대출 PIR을 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 13

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 기간 파라미터로 API에 직접 전달됨)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_apartment_mortgage_loan_pir(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "주택담보대출PIR", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 21: HAI (주택구매력지수)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_hai(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 HAI(주택구매력지수)를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 14

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11")
        period: 최근 N개월 (기본 12)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_hai(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "HAI(주택구매력지수)", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 22: KB-HOI (주택구입잠재력지수)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_hoi(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 KB-HOI(주택구입잠재력지수)를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 15

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 기간 파라미터로 API에 직접 전달됨)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_kb_housing_purchase_potential_index(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "KB-HOI(주택구입잠재력지수)", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 23: KB선도아파트50 지수
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_lead50(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 KB선도아파트50 지수를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 16

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_lead_apartment_50_index(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "KB선도아파트50지수", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 24: 시장동향/설문조사
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_market_trend(
    trend_type: str = "매수우위",
    cycle: str = "monthly",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 시장동향·설문조사 지수를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 21~26, 주간 5~8

    Args:
        trend_type: 지수 유형 ("매수우위", "매매거래활발", "전세수급", "전세거래활발",
                    "매매가격전망", "전세가격전망", 기본 "매수우위")
                    ※ 가격전망지수(매매·전세)는 월간만 지원됩니다.
        cycle: 주기 ("monthly"=월간, "weekly"=주간, 기본 "monthly")
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월·회차 (기본 12; 기간 파라미터로 API에 직접 전달됨)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    trend_c = _KB_MARKET_CODE.get(trend_type)
    cycle_c = _KB_CYCLE_CODE.get(cycle)
    if not trend_c:
        return json.dumps(
            {"error": f"지원하지 않는 trend_type: {trend_type}.",
             "options": list(_KB_MARKET_CODE.keys())},
            ensure_ascii=False, indent=2,
        )
    if not cycle_c:
        return json.dumps({"error": f"지원하지 않는 cycle: {cycle}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_market_trend(
            메뉴코드=trend_c,
            월간주간구분코드=cycle_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"시장동향/{trend_type}({cycle})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 25: 전세가격비율
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_jeonse_price_ratio(
    property_type: str = "APT",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 매매 대비 전세가격비율을 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 27~30

    Args:
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
        region_code: 지역코드 (예: "11"=서울, 기본 "11")
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}."}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_jeonse_price_ratio(
            매물종별구분=prop_c,
            지역코드=region_code,
        )
        return _kb_df_to_json(df, f"전세가격비율({property_type})", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# KB 도구 26: 전월세 전환율
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_jeonwolse_conversion_rate(
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 전월세 전환율을 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 59

    Args:
        region_code: 지역코드 (예: "11"=서울, 기본 "11"; 클라이언트 필터 적용)
        period: 최근 N개월 (기본 12; 클라이언트 날짜 필터 적용)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        api = Kbland()
        df = api.get_jeonwolse_conversion_rate(
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, "전월세전환율", region_code, period)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 27: 법정동코드 조회 (내장)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def rtms_get_lawd_codes(region: str = "") -> str:
    """내장된 법정동코드 매핑에서 지역명으로 코드를 조회합니다.

    Args:
        region: 검색할 지역명 (예: "강남", "서울", "경기"). 빈 문자열이면 전체 목록 반환.
    """
    if region:
        filtered = {k: v for k, v in LAWD_CD_MAP.items() if region in k}
    else:
        filtered = LAWD_CD_MAP

    return json.dumps({
        "query": region,
        "count": len(filtered),
        "results": filtered,
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 28: 공동주택공시가격 조회
# ---------------------------------------------------------------------------

APT_OFFICIAL_PRICE_URL = "http://apis.data.go.kr/1613000/AptPublpricInfoService1/getAptPublprcInfo"

# 주요 시군구 코드 (서울 전체 + 경기·광역시 주요 구)
_SIGUNGU_CODE_EXT = {
    **SEOUL_SIGUNGU_CODE,
    # 경기
    "성남시수정구": "41131", "성남시중원구": "41133", "성남시분당구": "41135",
    "수원시장안구": "41111", "수원시권선구": "41113", "수원시팔달구": "41115", "수원시영통구": "41117",
    "용인시처인구": "41461", "용인시기흥구": "41463", "용인시수지구": "41465",
    "안양시만안구": "41171", "안양시동안구": "41173",
    "고양시덕양구": "41281", "고양시일산동구": "41285", "고양시일산서구": "41287",
    "안산시상록구": "41271", "안산시단원구": "41273",
    "화성시": "41590", "과천시": "41290", "하남시": "41450",
    "부천시": "41190", "남양주시": "41360", "파주시": "41480",
    "의왕시": "41430", "군포시": "41410", "광명시": "41210",
    "평택시": "41220", "시흥시": "41390", "의정부시": "41150",
    # 부산
    "해운대구": "26350", "수영구": "26380", "부산진구": "26230",
    "남구": "26290", "동래구": "26260", "연제구": "26370",
    "사하구": "26380", "기장군": "26710",
    # 대구
    "수성구": "27260", "달서구": "27290", "달성군": "27710",
    # 인천
    "연수구": "28185", "남동구": "28200", "서구": "28237", "부평구": "28237",
    # 대전
    "서구": "30170", "유성구": "30200",
    # 광주
    "광산구": "29200",
}


def _resolve_sigungu_from_address(address: str) -> tuple[Optional[str], Optional[str]]:
    """지번/도로명 주소 문자열에서 (sigungu_cd, apt_name_hint) 추출.

    '강남구', '성남시분당구' 등 시군구 이름을 탐색한다. 더 긴 이름이 먼저 매칭되도록
    길이 내림차순 정렬한다.
    """
    sorted_entries = sorted(_SIGUNGU_CODE_EXT.items(), key=lambda x: len(x[0]), reverse=True)
    for dist_name, code in sorted_entries:
        if dist_name in address:
            idx = address.find(dist_name)
            remainder = address[idx + len(dist_name):].strip()
            parts = remainder.split()
            apt_parts = []
            for p in parts:
                # 숫자·번지(N-N)·도로명 suffix·행정동명 제거
                if re.match(r'^[\d\-]+$', p):
                    continue
                if re.search(r'(로|길|대로|번지)$', p):
                    continue
                # '삼성동', '역삼동' 같이 행정동 접미사 '동' 으로 끝나고 짧으면 제외
                if re.match(r'^.{2,4}동$', p):
                    continue
                apt_parts.append(p)
            apt_hint = apt_parts[0] if apt_parts else None
            return code, apt_hint
    return None, None


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def molit_get_apt_official_price(
    pub_year: Union[str, int],
    address: Optional[str] = None,
    apt_name: Optional[str] = None,
    dong_nm: Optional[str] = None,
    ho_nm: Optional[str] = None,
    kapt_code: Optional[str] = None,
) -> str:
    """공동주택공시가격을 조회합니다.

    아파트 주소(지번/도로명 모두 지원)와 동·호수로 해당 연도의 공동주택 공시가격을
    반환합니다. 주소에서 시군구와 단지명을 자동 추출합니다.

    Args:
        pub_year: 공시연도 (YYYY, 예: "2025"). 필수. 공시가격은 매년 4월 말 공시.
        address: 아파트 주소 (지번 또는 도로명). 단지명 포함 권장.
                 예: "서울 강남구 래미안삼성1차"
                     "서울 강남구 삼성동 169 래미안삼성1차"
                     "서울 강남구 삼성로 55 래미안삼성1차"
                 kapt_code 직접 지정 시 생략 가능.
        apt_name: 단지명. address와 별도로 지정하면 검색 정확도 향상.
                  예: "래미안삼성1차"
        dong_nm: 동명 필터 (예: "101동"). 지정 시 해당 동만 반환.
        ho_nm: 호수 필터 (예: "1001"). 지정 시 해당 호수만 반환.
        kapt_code: 단지코드 직접 지정. apt_search_complex 결과의 kaptCode 사용.
                   지정 시 address 조회 생략.
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."

    pub_year = str(pub_year).strip()

    # --- Step 1: kapt_code 결정 ---
    if not kapt_code:
        if not address and not apt_name:
            return json.dumps({
                "error": "address 또는 kapt_code 중 하나는 필수입니다.",
                "hint": "address 예: '서울 강남구 래미안삼성1차'. 또는 apt_search_complex로 kaptCode 조회 후 kapt_code 파라미터에 지정하세요.",
            }, ensure_ascii=False, indent=2)

        sigungu_cd, apt_hint = _resolve_sigungu_from_address(address or "")
        search_name = apt_name or apt_hint

        if not sigungu_cd:
            return json.dumps({
                "error": "주소에서 시군구를 인식하지 못했습니다.",
                "hint": "주소에 '강남구', '성남시분당구' 등의 시군구 이름을 포함하거나, apt_search_complex로 kaptCode를 조회 후 kapt_code 파라미터에 직접 지정하세요.",
                "address_received": address,
            }, ensure_ascii=False, indent=2)

        if not search_name:
            return json.dumps({
                "error": "단지명을 추출하지 못했습니다.",
                "hint": "address에 단지명을 포함하거나 apt_name 파라미터를 별도로 지정해주세요.",
                "example": "address='서울 강남구 래미안삼성1차' 또는 apt_name='래미안삼성1차'",
                "address_received": address,
            }, ensure_ascii=False, indent=2)

        try:
            root = await _get_xml(APT_LIST_URL, {
                "serviceKey": DATA_GO_KR_KEY,
                "numOfRows": "100",
                "pageNo": "1",
                "sggCd": sigungu_cd,
            })
            items = root.findall(".//item")
            matched = [
                {
                    "kaptCode": _txt(it, "kaptCode"),
                    "kaptName": _txt(it, "kaptName"),
                    "kaptAddr": _txt(it, "kaptAddr"),
                }
                for it in items
                if search_name in _txt(it, "kaptName")
            ]
        except Exception as e:
            return _err(e, "단지 검색 중 오류")

        if not matched:
            return json.dumps({
                "error": f"'{search_name}' 단지를 찾지 못했습니다 (시군구코드={sigungu_cd}).",
                "hint": "apt_search_complex 도구로 단지 목록을 확인 후 kapt_code 파라미터에 직접 지정하세요.",
                "searched": {"sigungu_cd": sigungu_cd, "apt_name": search_name},
            }, ensure_ascii=False, indent=2)

        if len(matched) > 1:
            return json.dumps({
                "error": f"'{search_name}' 이름을 가진 단지가 {len(matched)}개 검색됩니다. kapt_code를 직접 지정해주세요.",
                "candidates": matched,
                "hint": "위 kaptCode 중 하나를 kapt_code 파라미터에 지정하세요.",
            }, ensure_ascii=False, indent=2)

        kapt_code = matched[0]["kaptCode"]

    # --- Step 2: 공시가격 조회 ---
    try:
        params: dict = {
            "serviceKey": DATA_GO_KR_KEY,
            "kaptCode": kapt_code,
            "pblntfYear": pub_year,
            "numOfRows": "1000",
            "pageNo": "1",
        }
        if dong_nm:
            params["dongNm"] = dong_nm
        if ho_nm:
            params["hoNm"] = ho_nm

        root = await _get_xml(APT_OFFICIAL_PRICE_URL, params)
        items = root.findall(".//item")

        if not items:
            return json.dumps({
                "error": "공시가격 데이터가 없습니다.",
                "kapt_code": kapt_code,
                "pub_year": pub_year,
                "hint": "연도·단지코드를 확인하세요. 당해 공시가격은 4월 말 이후 조회 가능합니다.",
            }, ensure_ascii=False, indent=2)

        result = []
        for item in items:
            try:
                area = float(_txt(item, "excluUseAr") or "0")
            except ValueError:
                area = 0.0
            try:
                price = int((_txt(item, "pblntfPc") or "0").replace(",", ""))
            except ValueError:
                price = 0
            result.append({
                "dong_nm": _txt(item, "dongNm"),
                "ho_nm": _txt(item, "hoNm"),
                "area_m2": area,
                "area_pyeong": round(area / 3.305785, 1),
                "official_price_원": price,
                "pub_year": _txt(item, "pblntfYear") or pub_year,
            })

        return json.dumps({
            "kapt_code": kapt_code,
            "pub_year": pub_year,
            "dong_nm_filter": dong_nm,
            "ho_nm_filter": ho_nm,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e, "공시가격 조회 중 오류")


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
