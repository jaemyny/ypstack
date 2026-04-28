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


def _err(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"오류: HTTP {e.response.status_code}"
    if isinstance(e, httpx.TimeoutException):
        return "오류: 요청 시간 초과"
    return f"오류: {type(e).__name__} - {e}"


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
# 도구 7: 한국부동산원 가격지수
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def reb_get_price_index(
    year_month: str,
    stat_type: str = "매매",
    region: Optional[str] = None,
) -> str:
    """한국부동산원 R-ONE 가격지수를 조회합니다.

    Args:
        year_month: 조회년월 (YYYYMM, 예: "202403")
        stat_type: 통계 유형 ("매매", "전세", "월세" 중 하나, 기본 "매매")
        region: 지역명 필터 (선택, 예: "서울")
    """
    if not REB_API_KEY:
        return "오류: REB_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        params = {
            "serviceKey": REB_API_KEY,
            "numOfRows": "100",
            "pageNo": "1",
            "STAT_YM": year_month,
            "_type": "json",
        }
        raw_response = None
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(REB_BASE, params=params)
            r.raise_for_status()
            raw_response = r.text

        # JSON 응답 시도
        try:
            data = json.loads(raw_response)
            items = []
            # 응답 구조 탐색
            if isinstance(data, dict):
                body = data.get("response", data).get("body", data)
                items_raw = body.get("items", {})
                if isinstance(items_raw, dict):
                    items = items_raw.get("item", [])
                elif isinstance(items_raw, list):
                    items = items_raw
            elif isinstance(data, list):
                items = data

            if region:
                items = [i for i in items if region in str(i.get("regionNm", ""))]

            return json.dumps({
                "stat_type": stat_type,
                "year_month": year_month,
                "count": len(items),
                "data": items,
            }, ensure_ascii=False, indent=2)

        except (json.JSONDecodeError, AttributeError):
            # XML 폴백
            root = ET.fromstring(raw_response)
            xml_items = root.findall(".//item")
            result = []
            for item in xml_items:
                row = {child.tag: (child.text.strip() if child.text else "") for child in item}
                if region and region not in row.get("regionNm", ""):
                    continue
                result.append(row)

            return json.dumps({
                "stat_type": stat_type,
                "year_month": year_month,
                "count": len(result),
                "data": result,
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

    Args:
        stat_type: 통계 유형 ("매매지수", "전세지수", "HAI", "PIR" 중 하나, 기본 "매매지수")
        region_code: 지역코드 (예: "11"=서울, "41"=경기, 기본 "11")
        period: 최근 N개월 (기본 12)
    """
    if not HAS_KBLAND:
        return "오류: PublicDataReader 미설치. pip install PublicDataReader"
    try:
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
            df = api.get_pir(지역코드=region_code, 기간=str(period))
        else:
            return f"오류: 지원하지 않는 stat_type입니다. ('매매지수', '전세지수', 'HAI', 'PIR' 중 하나를 선택하세요)"

        return df.to_json(orient="records", force_ascii=False)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# 도구 9: 법정동코드 조회 (내장)
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
