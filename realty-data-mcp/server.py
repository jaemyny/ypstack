#!/usr/bin/env python3
"""
한국 부동산/경제/투자 데이터 MCP 서버 (realty-data-mcp)

지원 API:
- 통계청 KOSIS : 인구통계, 가구통계, 지역별 통계 검색
- 한국은행 ECOS: 금리, 경제지표
- 국토부 RTMS  : 아파트 실거래가 (매매/전세)

설치 방법: INSTALL.md 참고
API 키 발급: 각 API 발급처 안내 참고
  - KOSIS  : https://kosis.kr/openapi/index/index.jsp
  - ECOS   : https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary
  - RTMS   : https://www.data.go.kr (아파트매매실거래자료)
"""

import json
import os
from typing import Optional
import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("realty-data")

# ──────────────────────────────────────────────
# 환경변수  (mcp.json 의 env 블록에서 주입됨)
# ──────────────────────────────────────────────
KOSIS_API_KEY = os.getenv("KOSIS_API_KEY", "")
ECOS_API_KEY  = os.getenv("ECOS_API_KEY", "")
RTMS_API_KEY  = os.getenv("RTMS_API_KEY", "")

KOSIS_BASE = "https://kosis.kr/openapi"
ECOS_BASE  = "https://ecos.bok.or.kr/api"
RTMS_BASE  = "http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc"


# ──────────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────────
async def _get(url: str, params: dict) -> dict | list:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "오류: API 인증 실패. API 키를 확인하세요."
        if code == 429:
            return "오류: 요청 한도 초과. 잠시 후 다시 시도하세요."
        if code == 404:
            return "오류: 해당 데이터를 찾을 수 없습니다."
        return f"오류: API 요청 실패 (HTTP {code})"
    if isinstance(e, httpx.TimeoutException):
        return "오류: 요청 시간 초과. 다시 시도하세요."
    return f"오류: {type(e).__name__} - {e}"


# ──────────────────────────────────────────────
# KOSIS 통계청 API
# ──────────────────────────────────────────────

class KosisSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str = Field(
        ...,
        description="검색할 통계 키워드. 예: '인구', '가구', '주택', '혼인', '출생'",
        min_length=1, max_length=100,
    )
    limit: Optional[int] = Field(
        default=20,
        description="반환할 최대 결과 수 (1~100)",
        ge=1, le=100,
    )


@mcp.tool(
    name="kosis_search_stats",
    annotations={
        "title": "KOSIS 통계 검색",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def kosis_search_stats(params: KosisSearchInput) -> str:
    """통계청 KOSIS에서 키워드로 통계표를 검색합니다.

    orgId(기관코드)와 tblId(통계표ID)를 반환하며, 이 값을 kosis_get_data에
    전달해 실제 데이터를 조회할 수 있습니다.

    Args:
        params.keyword: 검색할 키워드 (예: '인구', '아파트', '출생')
        params.limit: 반환할 최대 결과 수

    Returns:
        JSON - 검색된 통계표 목록 (orgId, tblId, tblNm 포함)
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다. ~/.claude/mcp.json 의 env 블록을 확인하세요."
    try:
        data = await _get(
            f"{KOSIS_BASE}/statisticsSearch.do",
            {
                "method": "getList",
                "apiKey": KOSIS_API_KEY,
                "vwCd": "MT_ZTITLE",
                "parentListId": "",
                "searchNm": params.keyword,
                "format": "json",
                "jsonVD": "Y",
            },
        )
        items = data if isinstance(data, list) else data.get("items", [])
        items = items[: params.limit]
        result = [
            {
                "orgId": item.get("ORG_ID", ""),
                "tblId": item.get("TBL_ID", ""),
                "tblNm": item.get("TBL_NM", ""),
                "orgNm": item.get("ORG_NM", ""),
                "period": f"{item.get('STRT_PRD_DE','')}~{item.get('END_PRD_DE','')}",
            }
            for item in items
        ]
        return json.dumps(
            {"keyword": params.keyword, "total": len(result), "tables": result},
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


class KosisDataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    org_id: str = Field(
        ...,
        description="기관코드. kosis_search_stats로 조회 가능. 예: '101' (통계청)",
        min_length=1, max_length=20,
    )
    tbl_id: str = Field(
        ...,
        description="통계표ID. kosis_search_stats로 조회 가능. 예: 'DT_1B04005N'",
        min_length=1, max_length=50,
    )
    obj_l1: Optional[str] = Field(
        default="ALL",
        description="분류1 코드. 'ALL' 이면 전체. 특정 지역/항목 코드로 좁힐 수 있음. 예: '11'(서울), '11010+11020'",
    )
    obj_l2: Optional[str] = Field(
        default="ALL",
        description="분류2 코드. 'ALL' 이면 전체. 예: '000+035+040'",
    )
    itm_id: Optional[str] = Field(
        default="ALL",
        description="항목코드. 'ALL' 이면 전체. 예: 'T100+T220'",
    )
    prd_se: Optional[str] = Field(
        default="Y",
        description="수록주기. 'Y'=연간, 'M'=월간, 'Q'=분기. 기본값: 'Y'",
    )
    start_period: Optional[str] = Field(
        default=None,
        description="조회 시작 기간. 예: '202301' (월), '2023' (년)",
    )
    end_period: Optional[str] = Field(
        default=None,
        description="조회 종료 기간. 예: '202312' (월), '2023' (년)",
    )
    limit: Optional[int] = Field(default=100, description="반환할 최대 행 수", ge=1, le=1000)


@mcp.tool(
    name="kosis_get_data",
    annotations={
        "title": "KOSIS 통계 데이터 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def kosis_get_data(params: KosisDataInput) -> str:
    """KOSIS 통계표의 실제 데이터를 조회합니다.

    kosis_search_stats로 얻은 orgId와 tblId를 사용해 데이터를 가져옵니다.
    40,000셀 초과 시 obj_l1/obj_l2/itm_id로 범위를 좁혀 재요청하세요.

    Args:
        params.org_id     : 기관코드 (예: '101')
        params.tbl_id     : 통계표ID
        params.obj_l1     : 분류1 코드 ('ALL' 또는 특정 코드, '+' 로 다중 선택)
        params.obj_l2     : 분류2 코드
        params.itm_id     : 항목 코드
        params.prd_se     : 주기 ('Y'/'M'/'Q')
        params.start_period / end_period: 기간

    Returns:
        JSON - 통계 데이터 (C1_NM, C2_NM, ITM_NM, DT, PRD_DE 포함)
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        query: dict = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": params.org_id,
            "tblId": params.tbl_id,
            "itmId": params.itm_id or "ALL",
            "objL1": params.obj_l1 or "ALL",
            "objL2": params.obj_l2 or "ALL",
            "prdSe": params.prd_se or "Y",
            "format": "json",
            "jsonVD": "Y",
        }
        if params.start_period:
            query["startPrdDe"] = params.start_period
        if params.end_period:
            query["endPrdDe"] = params.end_period

        data = await _get(f"{KOSIS_BASE}/Param/statisticsParameterData.do", query)

        # 에러 응답 처리
        if isinstance(data, dict) and "err" in data:
            err = data["err"]
            msg = data.get("errMsg", "")
            if err == "31":
                return f"오류: 조회 결과가 40,000셀을 초과합니다. obj_l1/obj_l2/itm_id로 범위를 좁혀 재요청하세요. (원문: {msg})"
            return f"KOSIS API 오류 [{err}]: {msg}"

        rows = data if isinstance(data, list) else data.get("items", [])
        rows = rows[: params.limit]

        result = [
            {
                "period": row.get("PRD_DE", ""),
                "region": row.get("C1_NM", ""),
                "category": row.get("C2_NM", ""),
                "item": row.get("ITM_NM", ""),
                "value": row.get("DT", ""),
                "unit": row.get("UNIT_NM", ""),
                "c1_code": row.get("C1", ""),
                "c2_code": row.get("C2", ""),
                "itm_id": row.get("ITM_ID", ""),
            }
            for row in rows
        ]
        return json.dumps(
            {"orgId": params.org_id, "tblId": params.tbl_id, "count": len(result), "data": result},
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


class KosisPopulationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    region: Optional[str] = Field(
        default=None,
        description="지역명 필터. 예: '서울', '경기', '부산'. 없으면 전체 반환.",
    )
    year: Optional[str] = Field(
        default=None,
        description="조회 연도. 예: '2023'. 없으면 최근 데이터 반환.",
    )


@mcp.tool(
    name="kosis_get_population",
    annotations={
        "title": "지역별 인구 통계 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def kosis_get_population(params: KosisPopulationInput) -> str:
    """통계청 KOSIS에서 지역별 인구 통계를 조회합니다. (시도별 주민등록인구)

    Args:
        params.region: 지역 필터 (예: '서울', '경기'). None 이면 전국.
        params.year: 조회 연도 (예: '2023'). None 이면 최근.

    Returns:
        JSON - 지역별 인구수
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        query: dict = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": "101",
            "tblId": "DT_1B040A3",
            "itmId": "T20",
            "objL1": "ALL",
            "prdSe": "Y",
            "format": "json",
            "jsonVD": "Y",
        }
        if params.year:
            query["startPrdDe"] = params.year
            query["endPrdDe"] = params.year

        data = await _get(f"{KOSIS_BASE}/Param/statisticsParameterData.do", query)
        rows = data if isinstance(data, list) else data.get("items", [])

        result = []
        for row in rows:
            region_name = row.get("C1_NM", "")
            if params.region and params.region not in region_name:
                continue
            result.append(
                {
                    "period": row.get("PRD_DE", ""),
                    "region": region_name,
                    "population": row.get("DT", ""),
                    "unit": row.get("UNIT_NM", "명"),
                }
            )

        return json.dumps(
            {
                "region_filter": params.region or "전국",
                "year": params.year or "최근",
                "count": len(result),
                "data": result,
            },
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


class KosisHouseholdInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    region: Optional[str] = Field(
        default=None,
        description="지역명 필터. 예: '서울', '경기'. 없으면 전체.",
    )
    year: Optional[str] = Field(
        default=None,
        description="조회 연도. 예: '2023'.",
    )


@mcp.tool(
    name="kosis_get_household",
    annotations={
        "title": "지역별 가구 통계 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def kosis_get_household(params: KosisHouseholdInput) -> str:
    """통계청 KOSIS에서 지역별 세대(가구) 통계를 조회합니다.

    Args:
        params.region: 지역 필터 (예: '서울'). None 이면 전국.
        params.year: 조회 연도. None 이면 최근.

    Returns:
        JSON - 지역별 세대수 데이터
    """
    if not KOSIS_API_KEY:
        return "오류: KOSIS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        query: dict = {
            "method": "getList",
            "apiKey": KOSIS_API_KEY,
            "orgId": "101",
            "tblId": "DT_1B040B3",
            "itmId": "ALL",
            "objL1": "ALL",
            "prdSe": "Y",
            "format": "json",
            "jsonVD": "Y",
        }
        if params.year:
            query["startPrdDe"] = params.year
            query["endPrdDe"] = params.year

        data = await _get(f"{KOSIS_BASE}/Param/statisticsParameterData.do", query)
        rows = data if isinstance(data, list) else data.get("items", [])

        result = []
        for row in rows:
            region_name = row.get("C1_NM", "")
            if params.region and params.region not in region_name:
                continue
            result.append(
                {
                    "period": row.get("PRD_DE", ""),
                    "region": region_name,
                    "item": row.get("ITM_NM", ""),
                    "households": row.get("DT", ""),
                    "unit": row.get("UNIT_NM", "가구"),
                }
            )

        return json.dumps(
            {
                "region_filter": params.region or "전국",
                "year": params.year or "최근",
                "count": len(result),
                "data": result,
            },
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


# ──────────────────────────────────────────────
# 한국은행 ECOS API
# ──────────────────────────────────────────────

class EcosRateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    start_date: str = Field(
        ...,
        description="조회 시작일. 월별: 'YYYYMM', 일별: 'YYYYMMDD'. 예: '202301'",
        min_length=6, max_length=8,
    )
    end_date: str = Field(
        ...,
        description="조회 종료일. 예: '202312'",
        min_length=6, max_length=8,
    )
    stat_code: Optional[str] = Field(
        default="722Y001",
        description=(
            "통계코드. 기준금리: '722Y001', CD금리(91일): '817Y002', "
            "COFIX(신규취급액): '121Y006', 국고채(3년): '731Y003'. "
            "모를 경우 ecos_search_stats로 먼저 검색하세요."
        ),
    )
    cycle: Optional[str] = Field(
        default="MM",
        description="주기. 'DD'(일), 'MM'(월), 'QQ'(분기), 'YY'(연). 기본값: 'MM'",
    )


@mcp.tool(
    name="ecos_get_interest_rate",
    annotations={
        "title": "한국은행 금리 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ecos_get_interest_rate(params: EcosRateInput) -> str:
    """한국은행 ECOS API에서 금리/경제지표 데이터를 조회합니다.

    주요 stat_code:
    - '722Y001': 한국은행 기준금리
    - '817Y002': CD금리 (91일)
    - '121Y006': COFIX (신규취급액 기준)
    - '731Y003': 국고채 (3년)

    Args:
        params.start_date: 시작일 (예: '202301')
        params.end_date  : 종료일 (예: '202312')
        params.stat_code : 통계코드 (기본: 기준금리)
        params.cycle     : 주기 ('DD'/'MM'/'QQ'/'YY')

    Returns:
        JSON - 금리 시계열 데이터
    """
    if not ECOS_API_KEY:
        return "오류: ECOS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        url = (
            f"{ECOS_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr"
            f"/1/100/{params.stat_code}/{params.cycle}"
            f"/{params.start_date}/{params.end_date}"
        )
        data = await _get(url, {})
        rows = data.get("StatisticSearch", {}).get("row", [])
        result = [
            {
                "date": row.get("TIME", ""),
                "stat_name": row.get("STAT_NAME", ""),
                "item_name": row.get("ITEM_NAME1", ""),
                "value": row.get("DATA_VALUE", ""),
                "unit": row.get("UNIT_NAME", "%"),
            }
            for row in rows
        ]
        return json.dumps(
            {
                "stat_code": params.stat_code,
                "period": f"{params.start_date}~{params.end_date}",
                "count": len(result),
                "data": result,
            },
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


class EcosSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    keyword: str = Field(
        ...,
        description="검색할 경제지표 키워드. 예: '금리', '물가', 'GDP', '환율', '주택'",
        min_length=1, max_length=100,
    )
    limit: Optional[int] = Field(default=20, description="반환할 최대 결과 수", ge=1, le=100)


@mcp.tool(
    name="ecos_search_stats",
    annotations={
        "title": "한국은행 경제통계 검색",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def ecos_search_stats(params: EcosSearchInput) -> str:
    """한국은행 ECOS에서 경제통계 항목을 검색합니다.

    검색 결과의 stat_code 를 ecos_get_interest_rate 에 활용하세요.

    Args:
        params.keyword: 검색 키워드 (예: '기준금리', '소비자물가', 'GDP')
        params.limit  : 최대 결과 수

    Returns:
        JSON - 통계항목 목록 (stat_code, stat_name, cycle 포함)
    """
    if not ECOS_API_KEY:
        return "오류: ECOS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        url = f"{ECOS_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr/1/{params.limit}/{params.keyword}"
        data = await _get(url, {})
        rows = data.get("StatisticSearch", {}).get("row", [])
        result = [
            {
                "stat_code": row.get("STAT_CODE", ""),
                "stat_name": row.get("STAT_NAME", ""),
                "item_code": row.get("ITEM_CODE1", ""),
                "item_name": row.get("ITEM_NAME1", ""),
                "cycle": row.get("CYCLE", ""),
                "start_time": row.get("START_TIME", ""),
                "end_time": row.get("END_TIME", ""),
            }
            for row in rows
        ]
        return json.dumps(
            {"keyword": params.keyword, "count": len(result), "items": result},
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


# ──────────────────────────────────────────────
# 국토부 RTMS 아파트 실거래가 API
# ──────────────────────────────────────────────

# 주요 법정동코드 (앞 5자리)
LAWD_CD_MAP = {
    "서울": "11",
    "서울강남구": "11680", "서울서초구": "11650", "서울송파구": "11710",
    "서울마포구": "11440", "서울용산구": "11170", "서울성동구": "11200",
    "서울노원구": "11350", "서울강동구": "11740", "서울양천구": "11470",
    "서울영등포구": "11500", "서울강서구": "11500",
    "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "경기성남시분당구": "41135", "경기수원시": "41110",
    "경기용인시수지구": "41465", "경기화성시": "41590",
    "강원": "42", "충북": "43", "충남": "44", "전북": "45",
    "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


class RtmsTradeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lawd_cd: str = Field(
        ...,
        description=(
            "법정동코드 앞 5자리. 예: '11680'(강남구), '41135'(분당구). "
            "모를 경우 rtms_get_lawd_codes 로 먼저 조회하세요."
        ),
        min_length=2, max_length=10,
    )
    deal_ymd: str = Field(
        ...,
        description="거래 연월 (YYYYMM). 예: '202312'",
        min_length=6, max_length=6,
    )
    apt_name: Optional[str] = Field(
        default=None,
        description="아파트 이름 필터. 예: '래미안', '자이'. 없으면 전체.",
    )
    min_area: Optional[float] = Field(
        default=None,
        description="최소 전용면적 (㎡). 예: 59.0 (약 18평)",
    )
    max_area: Optional[float] = Field(
        default=None,
        description="최대 전용면적 (㎡). 예: 85.0 (약 26평)",
    )
    limit: Optional[int] = Field(default=50, description="반환할 최대 건수", ge=1, le=500)


@mcp.tool(
    name="rtms_get_apt_trade",
    annotations={
        "title": "아파트 매매 실거래가 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def rtms_get_apt_trade(params: RtmsTradeInput) -> str:
    """국토부 RTMS API에서 아파트 매매 실거래가를 조회합니다.

    Args:
        params.lawd_cd  : 법정동코드 5자리 (예: '11680' = 서울 강남구)
        params.deal_ymd : 거래연월 (예: '202312')
        params.apt_name : 아파트명 필터
        params.min_area / max_area: 면적 범위 필터 (㎡)
        params.limit    : 최대 결과 건수

    Returns:
        JSON - 아파트 매매 실거래 내역 (단지명, 면적, 거래금액, 층, 날짜 포함)
    """
    if not RTMS_API_KEY:
        return "오류: RTMS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        import xml.etree.ElementTree as ET

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{RTMS_BASE}/getRTMSDataSvcAptTradeDev",
                params={
                    "serviceKey": RTMS_API_KEY,
                    "LAWD_CD": params.lawd_cd,
                    "DEAL_YMD": params.deal_ymd,
                    "numOfRows": 1000,
                    "pageNo": 1,
                },
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items_el = root.find(".//items")
        if items_el is None:
            return json.dumps({"count": 0, "data": []}, ensure_ascii=False)

        result = []
        for item in items_el.findall("item"):
            def txt(tag: str) -> str:
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            area_raw = txt("전용면적")
            try:
                area = float(area_raw)
            except ValueError:
                area = 0.0

            apt_name_val = txt("아파트")
            if params.apt_name and params.apt_name not in apt_name_val:
                continue
            if params.min_area is not None and area < params.min_area:
                continue
            if params.max_area is not None and area > params.max_area:
                continue

            result.append(
                {
                    "apt_name": apt_name_val,
                    "area_m2": area,
                    "area_pyeong": round(area / 3.305785, 1),
                    "floor": txt("층"),
                    "price_만원": txt("거래금액").replace(",", ""),
                    "year": txt("년"),
                    "month": txt("월"),
                    "day": txt("일"),
                    "build_year": txt("건축년도"),
                    "dong": txt("법정동"),
                }
            )
            if len(result) >= params.limit:
                break

        result.sort(key=lambda x: int(x.get("price_만원", "0") or 0), reverse=True)
        return json.dumps(
            {
                "lawd_cd": params.lawd_cd,
                "deal_ymd": params.deal_ymd,
                "count": len(result),
                "data": result,
            },
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


class RtmsRentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lawd_cd: str = Field(..., description="법정동코드 5자리. 예: '11680'(강남구)", min_length=2, max_length=10)
    deal_ymd: str = Field(..., description="거래 연월 (YYYYMM). 예: '202312'", min_length=6, max_length=6)
    apt_name: Optional[str] = Field(default=None, description="아파트명 필터")
    limit: Optional[int] = Field(default=50, description="최대 건수", ge=1, le=500)


@mcp.tool(
    name="rtms_get_apt_rent",
    annotations={
        "title": "아파트 전월세 실거래 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def rtms_get_apt_rent(params: RtmsRentInput) -> str:
    """국토부 RTMS API에서 아파트 전월세 실거래 정보를 조회합니다.

    Args:
        params.lawd_cd  : 법정동코드 (예: '11680')
        params.deal_ymd : 거래연월 (예: '202312')
        params.apt_name : 아파트명 필터
        params.limit    : 최대 건수

    Returns:
        JSON - 전세/월세 거래 내역 (보증금, 월세, 면적, 층 포함)
    """
    if not RTMS_API_KEY:
        return "오류: RTMS_API_KEY 환경변수가 설정되지 않았습니다."
    try:
        import xml.etree.ElementTree as ET

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{RTMS_BASE}/getRTMSDataSvcAptRent",
                params={
                    "serviceKey": RTMS_API_KEY,
                    "LAWD_CD": params.lawd_cd,
                    "DEAL_YMD": params.deal_ymd,
                    "numOfRows": 1000,
                    "pageNo": 1,
                },
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items_el = root.find(".//items")
        if items_el is None:
            return json.dumps({"count": 0, "data": []}, ensure_ascii=False)

        result = []
        for item in items_el.findall("item"):
            def txt(tag: str) -> str:
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            apt_name_val = txt("아파트")
            if params.apt_name and params.apt_name not in apt_name_val:
                continue

            monthly = txt("월세금액")
            rent_type = "월세" if monthly and monthly != "0" else "전세"
            result.append(
                {
                    "apt_name": apt_name_val,
                    "rent_type": rent_type,
                    "deposit_만원": txt("보증금액").replace(",", ""),
                    "monthly_만원": monthly,
                    "area_m2": txt("전용면적"),
                    "floor": txt("층"),
                    "year": txt("년"),
                    "month": txt("월"),
                    "dong": txt("법정동"),
                }
            )
            if len(result) >= params.limit:
                break

        return json.dumps(
            {
                "lawd_cd": params.lawd_cd,
                "deal_ymd": params.deal_ymd,
                "count": len(result),
                "data": result,
            },
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return _api_error(e)


@mcp.tool(
    name="rtms_get_lawd_codes",
    annotations={
        "title": "주요 지역 법정동코드 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def rtms_get_lawd_codes(region: str = "") -> str:
    """아파트 실거래 조회에 필요한 주요 지역별 법정동코드를 반환합니다.

    법정동코드는 rtms_get_apt_trade, rtms_get_apt_rent 의 lawd_cd 파라미터에 사용합니다.

    Args:
        region: 검색할 지역명 (예: '서울', '경기', '강남'). 빈 문자열이면 전체 목록.

    Returns:
        JSON - 지역명과 법정동코드 목록
    """
    filtered = {
        name: code
        for name, code in LAWD_CD_MAP.items()
        if not region or region in name
    }
    return json.dumps(
        {"region_filter": region or "전체", "codes": filtered},
        ensure_ascii=False, indent=2,
    )


# ──────────────────────────────────────────────
# 서버 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
