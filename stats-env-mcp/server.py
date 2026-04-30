"""stats-env-mcp: 한국 환경 데이터 MCP 서버 (에어코리아 대기오염 + 서울 공원 + KOSIS 환경 통계)"""

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

mcp = FastMCP("stats-env")

AIRKOREA_BASE = "http://apis.data.go.kr/B552584"
SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
KOSIS_BASE = "https://kosis.kr/openapi"

_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

AQI_GRADE_MAP = {
    "1": "좋음",
    "2": "보통",
    "3": "나쁨",
    "4": "매우나쁨",
    1: "좋음",
    2: "보통",
    3: "나쁨",
    4: "매우나쁨",
}


def _get_data_go_key() -> Optional[str]:
    return os.environ.get("DATA_GO_KR_KEY")


def _get_seoul_key() -> Optional[str]:
    return os.environ.get("SEOUL_API_KEY")


def _get_kosis_key() -> Optional[str]:
    return os.environ.get("KOSIS_API_KEY")


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def airkorea_get_realtime_air(
    station_name: str,
    data_term: Optional[str] = "DAILY",
) -> str:
    """에어코리아 실시간 대기오염 측정 데이터 조회.

    Args:
        station_name: 측정소명 (예: "강남구", "중구", "종로구", "수원")
        data_term: 데이터 기간 (DAILY: 최근 24시간, MONTH: 최근 1개월, 3MONTH: 최근 3개월, 기본값: DAILY)
    """
    key = _get_data_go_key()
    if not key:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."

    url = f"{AIRKOREA_BASE}/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
    params = {
        "serviceKey": key,
        "returnType": "json",
        "numOfRows": 24,
        "pageNo": 1,
        "stationName": station_name,
        "dataTerm": data_term,
        "ver": "1.3",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("response", {}).get("body", {}).get("items", [])
    if not items:
        return json.dumps(
            {"error": "측정 데이터가 없습니다. 측정소명을 확인해 주세요.", "station_name": station_name},
            ensure_ascii=False,
            indent=2,
        )

    measurements = []
    for item in items:
        grade_raw = item.get("khaiGrade", "")
        grade_str = AQI_GRADE_MAP.get(grade_raw, grade_raw) if grade_raw else "-"
        measurements.append({
            "datetime": item.get("dataTime", ""),
            "pm10": item.get("pm10Value", "-"),
            "pm25": item.get("pm25Value", "-"),
            "o3": item.get("o3Value", "-"),
            "no2": item.get("no2Value", "-"),
            "co": item.get("coValue", "-"),
            "so2": item.get("so2Value", "-"),
            "aqi": item.get("khaiValue", "-"),
            "aqi_grade": grade_str,
        })

    result = {
        "station_name": station_name,
        "data_term": data_term,
        "count": len(measurements),
        "measurements": measurements,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def airkorea_get_station_list(addr: str) -> str:
    """에어코리아 대기오염 측정소 목록 조회.

    Args:
        addr: 주소 또는 지역명 (예: "서울", "강남", "경기", "인천")
    """
    key = _get_data_go_key()
    if not key:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."

    url = f"{AIRKOREA_BASE}/MsrstnInfoInqireSvc/getMsrstnList"
    params = {
        "serviceKey": key,
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "addr": addr,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "error": f"에어코리아 측정소 API 오류 (HTTP {e.response.status_code})",
            "hint": (
                "측정소 목록 API는 일시적으로 403 거부될 수 있습니다. "
                "실시간 측정값은 airkorea_get_realtime_air(station_name='강남구') 등으로 조회 가능."
            ),
            "addr": addr,
        }, ensure_ascii=False, indent=2)

    items = data.get("response", {}).get("body", {}).get("items", [])
    if not items:
        return json.dumps(
            {"error": "측정소를 찾을 수 없습니다.", "addr": addr},
            ensure_ascii=False,
            indent=2,
        )

    stations = []
    for item in items:
        stations.append({
            "name": item.get("stationName", ""),
            "address": item.get("addr", ""),
            "network_type": item.get("mangName", ""),
            "station_code": item.get("stationCode", ""),
            "latitude": item.get("dmY", ""),
            "longitude": item.get("dmX", ""),
        })

    result = {
        "addr": addr,
        "count": len(stations),
        "stations": stations,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def airkorea_get_region_avg(
    item_code: str = "PM25",
    search_date: str = "",
    data_gubun: Optional[str] = "DAILY",
) -> str:
    """에어코리아 시도별 대기오염 평균 통계 조회.
    ※ 주의: 에어코리아 API는 search_date 파라미터를 사실상 무시하고 항상 최근 30일치만 반환합니다.
       과거 시점 데이터는 KOSIS 환경통계 또는 에어코리아 웹사이트에서 직접 다운로드 필요.

    Args:
        item_code: 오염물질 코드 (PM10/PM25/O3/NO2/CO/SO2, 기본값: PM25)
        search_date: 조회 기준 연월 (YYYY-MM) — 정부 API 제약으로 무시됨
        data_gubun: 데이터 구분 (DAILY/MONTHLY, 기본값: DAILY)
    """
    key = _get_data_go_key()
    if not key:
        return "오류: DATA_GO_KR_KEY 환경변수가 설정되지 않았습니다."

    if not search_date:
        from datetime import date
        today = date.today()
        search_date = today.strftime("%Y-%m")

    url = f"{AIRKOREA_BASE}/ArpltnStatsSvc/getCtprvnMesureLIst"
    params = {
        "serviceKey": key,
        "returnType": "json",
        "numOfRows": 20,
        "pageNo": 1,
        "itemCode": item_code,
        "dataGubun": data_gubun,
        "searchCondition": "MONTH",
        "searchDate": search_date,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("response", {}).get("body", {}).get("items", [])
    if not items:
        return json.dumps(
            {"error": "데이터가 없습니다.", "item_code": item_code, "search_date": search_date},
            ensure_ascii=False,
            indent=2,
        )

    region_keys = [
        "seoul", "busan", "daegu", "incheon", "gwangju", "daejeon",
        "ulsan", "gyeonggi", "gangwon", "chungbuk", "chungnam",
        "jeonbuk", "jeonnam", "gyeongbuk", "gyeongnam", "jeju", "sejong",
    ]
    region_names = {
        "seoul": "서울", "busan": "부산", "daegu": "대구", "incheon": "인천",
        "gwangju": "광주", "daejeon": "대전", "ulsan": "울산", "gyeonggi": "경기",
        "gangwon": "강원", "chungbuk": "충북", "chungnam": "충남",
        "jeonbuk": "전북", "jeonnam": "전남", "gyeongbuk": "경북",
        "gyeongnam": "경남", "jeju": "제주", "sejong": "세종",
    }

    records = []
    for item in items:
        record = {"data_time": item.get("dataTime", "")}
        for rk in region_keys:
            val = item.get(rk)
            if val is not None:
                record[region_names.get(rk, rk)] = val
        records.append(record)

    result = {
        "item_code": item_code,
        "search_date_requested": search_date,
        "data_gubun": data_gubun,
        "count": len(records),
        "note": "에어코리아 API는 항상 최근 30일치 데이터만 반환합니다. records[0].data_time을 확인하세요.",
        "records": records,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def seoul_get_park_list(
    district: Optional[str] = None,
    park_type: Optional[str] = None,
) -> str:
    """서울 공원 정보 목록 조회.

    Args:
        district: 구명 필터 (선택, 예: "강남구", "마포구", "종로구")
        park_type: 공원 유형 필터 (선택, 예: "근린공원", "어린이공원", "소공원", "체육공원")
    """
    key = _get_seoul_key()
    if not key:
        return "오류: SEOUL_API_KEY 환경변수가 설정되지 않았습니다."

    # 서울 공원 API: SearchParkInfoService (구 searchParkInfo 대체)
    url = f"{SEOUL_BASE}/{key}/json/SearchParkInfoService/1/1000/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("SearchParkInfoService", {}).get("row", [])
    if not rows:
        result_info = data.get("SearchParkInfoService", {}).get("RESULT", {})
        msg = result_info.get("MESSAGE", "공원 데이터가 없습니다.")
        return json.dumps({"error": msg, "raw_keys": list(data.keys())}, ensure_ascii=False, indent=2)

    parks = []
    for row in rows:
        addr    = row.get("PARK_ADDR", "")
        rgn     = row.get("RGN", "")        # 자치구
        # district 필터: 주소 또는 자치구 컬럼
        if district and district not in addr and district not in rgn:
            continue

        parks.append({
            "name":      row.get("PARK_NM", ""),
            "address":   addr,
            "district":  rgn,
            "area":      row.get("AREA", ""),
            "open_date": row.get("OPEN_YMD", ""),
            "tel":       row.get("TELNO", ""),
            "latitude":  row.get("YCRD_G", ""),
            "longitude": row.get("XCRD_G", ""),
        })

    result = {
        "district_filter": district,
        "total_parks_in_db": data.get("SearchParkInfoService", {}).get("list_total_count", 0),
        "count": len(parks),
        "parks": parks,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def kosis_get_env_stats(
    keyword: str = "환경",
    year: Optional[str] = None,
) -> str:
    """KOSIS 환경 관련 통계표 검색.

    Args:
        keyword: 검색 키워드 (예: "환경", "대기오염", "수질", "폐기물", "녹지", "기후변화", "탄소")
                 ※ "온실가스"는 KOSIS에 등록된 표제어가 아닙니다 — "기후변화" 또는 "탄소"로 검색하세요.
        year: 기준 연도 (선택, 예: "2023")
    """
    key = _get_kosis_key()
    if not key:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."

    # MCP 런타임이 year를 int로 전달하는 경우 대비
    year = str(year) if year is not None else None

    search_kwd = keyword
    if year:
        search_kwd += f" {year}"

    url = f"{KOSIS_BASE}/statisticsSearch.do"
    params = {
        "method": "getList",
        "apiKey": key,
        "vwCd": "MT_ZTITLE",
        "parentListId": "",
        "searchNm": search_kwd,
        "format": "json",
        "jsonVD": "Y",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if isinstance(data, list):
        items = data[:20]
        result = {
            "keyword": keyword,
            "year": year,
            "count": len(items),
            "stats": [
                {
                    "org_id": item.get("orgId", ""),
                    "table_id": item.get("tblId", ""),
                    "table_nm": item.get("tblNm", ""),
                    "org_nm": item.get("orgNm", ""),
                    "stats_knd": item.get("statsKnd", ""),
                }
                for item in items
            ],
        }
    else:
        result = {"keyword": keyword, "raw": data}

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
