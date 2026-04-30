#!/usr/bin/env python3
"""
stats-realty-mcp: 한국 부동산 실거래가 · 가격지수 · 공급 · 단지 정보
- 국토부 RTMS: 아파트 매매/전월세/분양권전매 실거래가
- 한국부동산원 R-ONE: 가격지수, 전세가율
- 국토부: 공동주택 단지 목록/기본정보, 주택 인허가
- KB부동산: 가격지수·HAI·PIR (PublicDataReader, 무키)
"""
import json, os, xml.etree.ElementTree as ET
from typing import Optional
import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stats-realty")

DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_KEY", "")
REB_API_KEY    = os.getenv("REB_API_KEY", "")
KOSIS_API_KEY  = os.getenv("KOSIS_API_KEY", "")

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
    "서울": "11", "서울종로구": "11010", "서울중구": "11020",
    "서울용산구": "11030", "서울성동구": "11040", "서울광진구": "11050",
    "서울동대문구": "11060", "서울중랑구": "11070", "서울성북구": "11080",
    "서울강북구": "11090", "서울도봉구": "11100", "서울노원구": "11110",
    "서울은평구": "11120", "서울서대문구": "11130", "서울마포구": "11140",
    "서울양천구": "11150", "서울강서구": "11160", "서울구로구": "11170",
    "서울금천구": "11180", "서울영등포구": "11190", "서울동작구": "11200",
    "서울관악구": "11210", "서울서초구": "11220", "서울강남구": "11230",
    "서울송파구": "11240", "서울강동구": "11250",
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
        lawd_cd: 법정동코드 앞 5자리 (예: "11230" = 서울 강남구)
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
        lawd_cd: 법정동코드 앞 5자리 (예: "11230" = 서울 강남구)
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
        lawd_cd: 법정동코드 앞 5자리 (예: "11230" = 서울 강남구)
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
    sigungu_cd: str,
    apt_name: Optional[str] = None,
    limit: Optional[int] = 20,
) -> str:
    """공동주택 단지 목록을 조회합니다.

    Args:
        sigungu_cd: 시군구코드 5자리 (예: "11230" = 강남구)
        apt_name: 아파트명 필터 (선택)
        limit: 최대 반환 건수 (기본 20)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
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
    sido: str,
    year_month: str,
    limit: Optional[int] = 50,
) -> str:
    """국토부 주택 인허가 실적을 조회합니다.

    Args:
        sido: 시도명 (예: "서울특별시", "경기도")
        year_month: 조회 기간 (YYYYMM 또는 YYYY)
        limit: 최대 반환 건수 (기본 50)
    """
    if not DATA_GO_KR_KEY:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."
    try:
        # 4자리 연도인 경우 해당 연도 전체로 처리
        if len(year_month) == 4:
            start_ymd = year_month + "01"
            end_ymd = year_month + "12"
        else:
            start_ymd = year_month
            end_ymd = year_month

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
# 도구 7: 한국부동산원 아파트 가격지수 (KOSIS 경유 — orgId=408)
# ---------------------------------------------------------------------------

_REB_TBL = {
    "매매": ("408", "DT_304004_WEEK_002_B"),  # 주간 아파트 매매가격지수
    "전세": ("408", "DT_304004_WEEK_004_A"),  # 주간 아파트 전세가격지수
}

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def reb_get_price_index(
    year_month: str,
    stat_type: str = "매매",
    region: Optional[str] = None,
) -> str:
    """한국부동산원 아파트 가격지수를 조회합니다 (KOSIS 한국부동산원, 주간).

    Args:
        year_month: 조회년월 (YYYYMM, 예: "202503") — 해당 월의 주간 데이터를 반환
        stat_type: 통계 유형 ("매매" 또는 "전세", 기본 "매매")
        region: 지역명 필터 (선택, 예: "서울", "수도권", "전국")
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
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
            rows = [r for r in rows if region in r.get("C1_NM", "")]

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
# 도구 8: KB부동산 통계 (PublicDataReader)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_price_stats(
    stat_type: str = "매매지수",
    region_code: str = "11",
    period: Optional[int] = 12,
) -> str:
    """KB부동산 가격통계를 조회합니다 (PublicDataReader, API 키 불필요).
    DEPRECATED: kb_get_price_index / kb_get_hai / kb_get_pir 개별 도구 사용을 권장합니다.

    Args:
        stat_type: 통계 유형 ("매매지수", "전세지수", "HAI", "PIR" 중 하나, 기본 "매매지수")
        region_code: 지역코드 (예: "11"=서울, "41"=경기, 기본 "11")
        period: 최근 N개월 (기본 12)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
        import pandas as pd
        api = Kbland()
        if stat_type == "매매지수":
            df = api.get_price_index(
                월간주간구분코드="01",
                매물종별구분="01",
                매매전세코드="01",
                지역코드=region_code,
                기간=str(period),
            )
        elif stat_type == "전세지수":
            df = api.get_price_index(
                월간주간구분코드="01",
                매물종별구분="01",
                매매전세코드="02",
                지역코드=region_code,
                기간=str(period),
            )
        elif stat_type == "HAI":
            df = api.get_hai(지역코드=region_code, 기간=str(period))
        elif stat_type == "PIR":
            df = api.get_pir("01", 지역코드=region_code, 기간=str(period))
        else:
            return f"오류: 지원하지 않는 stat_type입니다. ('매매지수', '전세지수', 'HAI', 'PIR' 중 하나를 선택하세요)"

        # PublicDataReader가 None 반환하는 경우 (지원하지 않는 지역코드)
        if df is None:
            return json.dumps({
                "error": (
                    f"지역코드 '{region_code}'에 대한 KB부동산 데이터를 불러오지 못했습니다. "
                    "KB부동산 API는 광역시도 단위 일부만 지원합니다."
                ),
                "supported_codes": {
                    "11": "서울특별시", "21": "부산광역시", "22": "대구광역시",
                    "23": "인천광역시", "24": "광주광역시", "25": "대전광역시",
                    "26": "울산광역시", "29": "세종특별자치시",
                    "주의": "경기(41/42), 강원, 충청, 전라, 경상 등 도단위는 KB API에서 미지원될 수 있습니다.",
                },
                "stat_type": stat_type,
                "region_code": region_code,
            }, ensure_ascii=False, indent=2)

        # 지역코드 필터 (API가 region_code를 무시하는 경우 대응)
        region_cols = [c for c in df.columns if "지역코드" in c]
        if region_cols:
            rc = region_cols[0]
            df = df[df[rc].astype(str).str.startswith(region_code.zfill(2))].copy()

        # 날짜 컬럼으로 최근 N개월만 자르기 (기간 파라미터가 무시되는 API 대응)
        date_cols = [c for c in df.columns if "날짜" in c or "date" in c.lower() or "ym" in c.lower()]
        if date_cols and period:
            dc = date_cols[0]
            df[dc] = pd.to_datetime(df[dc], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=period)
            df = df[df[dc] >= cutoff].copy()
            df[dc] = df[dc].dt.strftime("%Y-%m")

        result = json.loads(df.to_json(orient="records", force_ascii=False))
        return json.dumps({
            "stat_type": stat_type,
            "region_code": region_code,
            "period_months": period,
            "count": len(result),
            "data": result,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(e)


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
                "error": f"지역코드 '{region_code}'에 대한 KB 데이터를 불러오지 못했습니다. "
                         "KB부동산 API는 광역시도 단위 일부만 지원합니다.",
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
    """KB부동산 주택가격지수를 조회합니다 (PublicDataReader, API 키 불필요).
    엑셀 매핑: 월간 1~8, 주간 3~4

    Args:
        cycle: 주기 ("monthly"=월간, "weekly"=주간, 기본 "monthly")
        property_type: 매물종별 ("APT", "연립", "단독", "종합", 기본 "APT")
              ※ APT 외 매물종별은 월간 데이터만 지원됩니다.
        deal_type: 거래유형 ("매매" 또는 "전세", 기본 "매매")
        region_code: 지역코드 (예: "11"=서울, 기본 "11")
        period: 최근 N개월·회차 (기본 12)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    cycle_c = _KB_CYCLE_CODE.get(cycle)
    if not cycle_c:
        return json.dumps({"error": f"지원하지 않는 cycle: {cycle}. ('monthly' 또는 'weekly')"}, ensure_ascii=False, indent=2)
    prop_c = _KB_PROPERTY_CODE.get(property_type)
    if not prop_c:
        return json.dumps({"error": f"지원하지 않는 property_type: {property_type}. ('APT','연립','단독','종합')"}, ensure_ascii=False, indent=2)
    deal_c = _KB_DEAL_CODE.get(deal_type)
    if not deal_c:
        return json.dumps({"error": f"지원하지 않는 deal_type: {deal_type}. ('매매' 또는 '전세')"}, ensure_ascii=False, indent=2)
    try:
        api = Kbland()
        df = api.get_price_index(
            월간주간구분코드=cycle_c,
            매물종별구분=prop_c,
            매매전세코드=deal_c,
            지역코드=region_code,
            기간=str(period) if period else "12",
        )
        return _kb_df_to_json(df, f"가격지수({cycle}/{property_type}/{deal_type})", region_code, period)
    except Exception as e:
        return _err(e)


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
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
