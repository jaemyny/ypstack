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

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

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

    Args:
        item_code: 오염물질 코드 (PM10/PM25/O3/NO2/CO/SO2, 기본값: PM25)
        search_date: 조회 기준 연월 (YYYY-MM, 예: "2024-01")
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
        "search_date": search_date,
        "data_gubun": data_gubun,
        "count": len(records),
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

    url = f"{SEOUL_BASE}/{key}/json/searchParkInfo/1/100/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("searchParkInfo", {}).get("row", [])
    if not rows:
        return json.dumps({"error": "공원 데이터가 없습니다."}, ensure_ascii=False, indent=2)

    parks = []
    for row in rows:
        addr = row.get("P_ADDR", "")
        p_type = row.get("P_LIST_CONTENT", "")
        p_zone = row.get("P_ZONE", "")

        if district and district not in addr and district not in p_zone:
            continue
        if park_type and park_type not in p_type:
            continue

        parks.append({
            "name": row.get("P_PARK", ""),
            "address": addr,
            "type": p_type,
            "zone": p_zone,
            "latitude": row.get("LATITUDE", ""),
            "longitude": row.get("LONGITUDE", ""),
        })

    result = {
        "district_filter": district,
        "park_type_filter": park_type,
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
        keyword: 검색 키워드 (예: "환경", "대기오염", "수질", "폐기물", "녹지", "온실가스")
        year: 기준 연도 (선택, 예: "2023")
    """
    key = _get_kosis_key()
    if not key:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."

    search_kwd = keyword
    if year:
        search_kwd += f" {year}"

    url = f"{KOSIS_BASE}/statisticsList.do"
    params = {
        "method": "getList",
        "apiKey": key,
        "vwCd": "MT_ZTITLE",
        "parentListId": "K",
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
