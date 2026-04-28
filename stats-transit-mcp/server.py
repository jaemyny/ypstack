"""stats-transit-mcp: 한국 교통 데이터 MCP 서버 (서울 지하철/버스 + KOSIS 통계)"""

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

mcp = FastMCP("stats-transit")

SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
KOSIS_BASE = "https://kosis.kr/openapi"

_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

# 주요 지하철역 내장 데이터 (30개 이상)
STATION_DATA = {
    "강남": {"lines": ["2호선"], "lat": 37.4979, "lng": 127.0276, "district": "강남구"},
    "홍대입구": {"lines": ["2호선", "공항철도", "경의중앙선"], "lat": 37.5572, "lng": 126.9247, "district": "마포구"},
    "신촌": {"lines": ["2호선"], "lat": 37.5551, "lng": 126.9368, "district": "서대문구"},
    "건대입구": {"lines": ["2호선", "7호선"], "lat": 37.5403, "lng": 127.0694, "district": "광진구"},
    "신림": {"lines": ["2호선"], "lat": 37.4845, "lng": 126.9298, "district": "관악구"},
    "구로디지털단지": {"lines": ["2호선"], "lat": 37.4853, "lng": 126.9014, "district": "구로구"},
    "신도림": {"lines": ["1호선", "2호선"], "lat": 37.5086, "lng": 126.8913, "district": "구로구"},
    "잠실": {"lines": ["2호선", "8호선"], "lat": 37.5133, "lng": 127.1001, "district": "송파구"},
    "사당": {"lines": ["2호선", "4호선"], "lat": 37.4764, "lng": 126.9816, "district": "동작구"},
    "교대": {"lines": ["2호선", "3호선"], "lat": 37.4934, "lng": 127.0139, "district": "서초구"},
    "선릉": {"lines": ["2호선", "분당선"], "lat": 37.5045, "lng": 127.0495, "district": "강남구"},
    "역삼": {"lines": ["2호선"], "lat": 37.5007, "lng": 127.0362, "district": "강남구"},
    "서울역": {"lines": ["1호선", "4호선", "공항철도", "경의중앙선"], "lat": 37.5545, "lng": 126.9707, "district": "중구"},
    "종로3가": {"lines": ["1호선", "3호선", "5호선"], "lat": 37.5712, "lng": 126.9919, "district": "종로구"},
    "동대문": {"lines": ["1호선", "4호선"], "lat": 37.5714, "lng": 127.0101, "district": "종로구"},
    "왕십리": {"lines": ["2호선", "5호선", "경의중앙선", "분당선"], "lat": 37.5614, "lng": 127.0374, "district": "성동구"},
    "합정": {"lines": ["2호선", "6호선"], "lat": 37.5498, "lng": 126.9147, "district": "마포구"},
    "이대": {"lines": ["2호선"], "lat": 37.5562, "lng": 126.9464, "district": "서대문구"},
    "충정로": {"lines": ["2호선", "5호선"], "lat": 37.5600, "lng": 126.9637, "district": "서대문구"},
    "강변": {"lines": ["2호선"], "lat": 37.5364, "lng": 127.0943, "district": "광진구"},
    "삼성": {"lines": ["2호선"], "lat": 37.5088, "lng": 127.0632, "district": "강남구"},
    "천호": {"lines": ["5호선", "8호선"], "lat": 37.5386, "lng": 127.1236, "district": "강동구"},
    "광화문": {"lines": ["5호선"], "lat": 37.5718, "lng": 126.9769, "district": "종로구"},
    "여의도": {"lines": ["5호선", "9호선"], "lat": 37.5219, "lng": 126.9240, "district": "영등포구"},
    "영등포구청": {"lines": ["2호선", "5호선"], "lat": 37.5259, "lng": 126.8963, "district": "영등포구"},
    "신사": {"lines": ["3호선"], "lat": 37.5152, "lng": 127.0200, "district": "강남구"},
    "압구정": {"lines": ["3호선"], "lat": 37.5274, "lng": 127.0282, "district": "강남구"},
    "대치": {"lines": ["3호선"], "lat": 37.4945, "lng": 127.0607, "district": "강남구"},
    "도곡": {"lines": ["3호선", "분당선"], "lat": 37.4935, "lng": 127.0436, "district": "강남구"},
    "노원": {"lines": ["4호선", "7호선"], "lat": 37.6555, "lng": 127.0563, "district": "노원구"},
    "수유": {"lines": ["4호선"], "lat": 37.6378, "lng": 127.0253, "district": "강북구"},
    "미아사거리": {"lines": ["4호선"], "lat": 37.6132, "lng": 127.0302, "district": "강북구"},
    "길음": {"lines": ["4호선"], "lat": 37.6030, "lng": 127.0256, "district": "성북구"},
    "공덕": {"lines": ["5호선", "6호선", "공항철도", "경의중앙선"], "lat": 37.5448, "lng": 126.9516, "district": "마포구"},
    "마포": {"lines": ["5호선"], "lat": 37.5437, "lng": 126.9478, "district": "마포구"},
}


def _get_seoul_key() -> Optional[str]:
    return os.environ.get("SEOUL_API_KEY")


def _get_kosis_key() -> Optional[str]:
    return os.environ.get("KOSIS_API_KEY")


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def seoul_get_subway_ridership(
    year: str,
    line: Optional[str] = None,
) -> str:
    """전국 지하철 노선별 연간 수송인원 통계 조회 (KOSIS).

    Args:
        year: 조회 연도 (YYYY, 예: "2023")
        line: 호선 필터 (선택, 예: "1호선", "2호선", "합계")
    """
    key = _get_kosis_key()
    if not key:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."

    url = f"{KOSIS_BASE}/Param/statisticsParameterData.do"
    params = {
        "method": "getList",
        "apiKey": key,
        "orgId": "201",
        "tblId": "DT_201004_O100011",
        "itmId": "T001",          # 수송인원
        "objL1": "ALL",
        "prdSe": "Y",
        "startPrdDe": year,
        "endPrdDe": year,
        "format": "json",
        "jsonVD": "Y",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if isinstance(data, dict) and data.get("err"):
        return json.dumps({"error": f"KOSIS 오류: {data.get('errMsg', data)}"}, ensure_ascii=False, indent=2)

    rows = data if isinstance(data, list) else []

    records = []
    for row in rows:
        nm = row.get("C1_NM", "")
        if line and line not in nm:
            continue
        records.append({
            "line": nm,
            "year": row.get("PRD_DE", ""),
            "passengers_1000": row.get("DT", ""),
            "unit": row.get("UNIT_NM", "천명"),
        })

    result = {
        "year": year,
        "line_filter": line,
        "count": len(records),
        "note": "수송인원 단위: 천명",
        "data": records,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def seoul_get_subway_realtime(station_name: str) -> str:
    """서울 지하철 실시간 도착 정보 조회.

    Args:
        station_name: 역명 (예: "강남", "홍대입구", "서울역")
    """
    key = _get_seoul_key()
    if not key:
        return "오류: SEOUL_API_KEY 환경변수가 설정되지 않았습니다."

    url = f"{SEOUL_BASE}/{key}/json/realtimeStationArrival/1/10/{station_name}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("realtimeStationArrival", {}).get("row", [])
    if not rows:
        error_msg = data.get("RESULT", {}).get("MESSAGE", "데이터가 없습니다.")
        return json.dumps({"error": error_msg, "station_name": station_name}, ensure_ascii=False, indent=2)

    arrivals = []
    for row in rows:
        arrivals.append({
            "subway_id": row.get("subwayId", ""),
            "line_nm": row.get("trainLineNm", ""),
            "arrival_msg": row.get("arvlMsg2", ""),
            "current_station": row.get("arvlMsg3", ""),
            "terminal_station": row.get("bstatnNm", ""),
            "order_key": row.get("ordkey", ""),
        })

    result = {
        "station_name": station_name,
        "count": len(arrivals),
        "arrivals": arrivals,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def seoul_get_bus_route_info(bus_number: str) -> str:
    """서울 버스 노선 정보 조회.

    Args:
        bus_number: 버스 번호 (예: "370", "9714", "146")
    """
    key = _get_seoul_key()
    if not key:
        return "오류: SEOUL_API_KEY 환경변수가 설정되지 않았습니다."

    url = f"{SEOUL_BASE}/{key}/json/busRouteList/1/10/{bus_number}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("busRouteList", {}).get("row", [])
    if not rows:
        return json.dumps({"error": "해당 버스 노선을 찾을 수 없습니다.", "bus_number": bus_number}, ensure_ascii=False, indent=2)

    routes = []
    for row in rows:
        routes.append({
            "route_nm": row.get("busRouteNm", ""),
            "start_station": row.get("stSttnNm", ""),
            "end_station": row.get("edSttnNm", ""),
            "interval_min": row.get("term", ""),
            "first_bus_time": row.get("firstBusTm", ""),
            "last_bus_time": row.get("lastBusTm", ""),
        })

    result = {
        "bus_number": bus_number,
        "count": len(routes),
        "routes": routes,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def kosis_get_transit_stats(
    keyword: str = "교통",
    year: Optional[str] = None,
    region: Optional[str] = None,
) -> str:
    """KOSIS 교통 관련 통계표 검색.

    Args:
        keyword: 검색 키워드 (예: "교통", "지하철", "버스", "교통량")
        year: 기준 연도 (선택, 예: "2023")
        region: 지역명 (선택, 예: "서울", "경기")
    """
    key = _get_kosis_key()
    if not key:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."

    search_kwd = keyword
    if year:
        search_kwd += f" {year}"
    if region:
        search_kwd += f" {region}"

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
            "region": region,
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


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def seoul_get_station_info(
    station_name: Optional[str] = "",
    line: Optional[str] = "",
) -> str:
    """서울 주요 지하철역 정보 조회 (내장 데이터, 30개 이상 수록).

    Args:
        station_name: 역명 검색어 (선택, 예: "강남", "역삼")
        line: 호선 필터 (선택, 예: "2호선", "3호선", "5호선")
    """
    filtered = {}
    for name, info in STATION_DATA.items():
        if station_name and station_name not in name:
            continue
        if line and line not in info.get("lines", []):
            continue
        filtered[name] = info

    stations_list = [
        {
            "station_nm": name,
            "lines": info["lines"],
            "latitude": info["lat"],
            "longitude": info["lng"],
            "district": info["district"],
        }
        for name, info in filtered.items()
    ]

    result = {
        "query_station": station_name,
        "query_line": line,
        "count": len(stations_list),
        "stations": stations_list,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
