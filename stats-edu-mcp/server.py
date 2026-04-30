"""stats-edu-mcp: 한국 교육 데이터 MCP 서버 (NEIS 학교/학원 정보 + KOSIS 교육 통계)"""

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

mcp = FastMCP("stats-edu")

NEIS_BASE = "https://open.neis.go.kr/hub"
KOSIS_BASE = "https://kosis.kr/openapi"

_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

# 지역 → 교육청 코드 매핑
REGION_CODE_MAP = {
    "서울특별시": "B10",
    "서울": "B10",
    "부산광역시": "C10",
    "부산": "C10",
    "대구광역시": "D10",
    "대구": "D10",
    "인천광역시": "E10",
    "인천": "E10",
    "광주광역시": "F10",
    "광주": "F10",
    "대전광역시": "G10",
    "대전": "G10",
    "울산광역시": "H10",
    "울산": "H10",
    "세종특별자치시": "I10",
    "세종": "I10",
    "경기도": "J10",
    "경기": "J10",
    "강원특별자치도": "K10",
    "강원도": "K10",
    "강원": "K10",
    "충청북도": "M10",
    "충북": "M10",
    "충청남도": "N10",
    "충남": "N10",
    "전북특별자치도": "P10",
    "전라북도": "P10",
    "전북": "P10",
    "전라남도": "Q10",
    "전남": "Q10",
    "경상북도": "R10",
    "경북": "R10",
    "경상남도": "S10",
    "경남": "S10",
    "제주특별자치도": "T10",
    "제주": "T10",
}


def _get_neis_key() -> Optional[str]:
    return os.environ.get("NEIS_API_KEY")


def _get_kosis_key() -> Optional[str]:
    return os.environ.get("KOSIS_API_KEY")


def _get_edu_code(region: str) -> str:
    """지역명으로 교육청 코드 반환. 매핑 없으면 B10(서울) 기본값."""
    for key, code in REGION_CODE_MAP.items():
        if key in region:
            return code
    return "B10"


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def neis_get_school_list(
    region: str,
    school_type: Optional[str] = "초등학교",
    district: Optional[str] = None,
    limit: Optional[int] = 50,
) -> str:
    """NEIS 학교 목록 조회.

    Args:
        region: 지역명 (예: "서울특별시", "경기도", "부산광역시")
        school_type: 학교급 (예: "초등학교", "중학교", "고등학교", 기본값: "초등학교")
        district: 구/군명 필터 (선택, 예: "강남구", "분당구")
        limit: 최대 결과 수 (기본값: 50, 최대 1000)
    """
    key = _get_neis_key()
    if not key:
        return "오류: NEIS_API_KEY 환경변수가 설정되지 않았습니다."

    edu_code = _get_edu_code(region)
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000 if district else min(limit, 1000),
        "ATPT_OFCDC_SC_CODE": edu_code,
        "SCHUL_KND_SC_NM": school_type,
    }

    url = f"{NEIS_BASE}/schoolInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("schoolInfo", [{}])[1].get("row", []) if len(data.get("schoolInfo", [])) > 1 else []
    if not rows:
        error_info = data.get("RESULT", {})
        return json.dumps(
            {"error": error_info.get("MESSAGE", "데이터가 없습니다."), "region": region, "school_type": school_type},
            ensure_ascii=False,
            indent=2,
        )

    schools = []
    for row in rows:
        addr = row.get("ORG_RDNMA", "")
        if district and district not in addr:
            continue
        schools.append({
            "name": row.get("SCHUL_NM", ""),
            "type": row.get("SCHUL_KND_SC_NM", ""),
            "address": addr,
            "phone": row.get("ORG_TELNO", ""),
            "founded": row.get("FOND_YMD", ""),
            "student_count": row.get("PUPIL_CNT", ""),
        })

    result = {
        "region": region,
        "edu_code": edu_code,
        "school_type": school_type,
        "district_filter": district,
        "count": len(schools),
        "schools": schools,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def neis_get_school_detail(
    school_name: str,
    region: Optional[str] = "서울특별시",
) -> str:
    """NEIS 학교 상세 정보 조회.

    Args:
        school_name: 학교명 (예: "대치초등학교", "휘문중학교")
        region: 지역명 (선택, 기본값: "서울특별시")
    """
    key = _get_neis_key()
    if not key:
        return "오류: NEIS_API_KEY 환경변수가 설정되지 않았습니다."

    edu_code = _get_edu_code(region)
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 10,
        "ATPT_OFCDC_SC_CODE": edu_code,
        "SCHUL_NM": school_name,
    }

    url = f"{NEIS_BASE}/schoolInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("schoolInfo", [{}])[1].get("row", []) if len(data.get("schoolInfo", [])) > 1 else []
    if not rows:
        error_info = data.get("RESULT", {})
        return json.dumps(
            {"error": error_info.get("MESSAGE", "해당 학교를 찾을 수 없습니다."), "school_name": school_name},
            ensure_ascii=False,
            indent=2,
        )

    schools = []
    for row in rows:
        schools.append({
            "name": row.get("SCHUL_NM", ""),
            "type": row.get("SCHUL_KND_SC_NM", ""),
            "edu_office": row.get("ATPT_OFCDC_SC_NM", ""),
            "address": row.get("ORG_RDNMA", ""),
            "phone": row.get("ORG_TELNO", ""),
            "founded": row.get("FOND_YMD", ""),
            "student_count": row.get("PUPIL_CNT", ""),
            "fax": row.get("ORG_FAXNO", ""),
            "homepage": row.get("HMPG_ADRES", ""),
            "co_ed": row.get("COEDU_SC_NM", ""),
        })

    result = {
        "school_name": school_name,
        "region": region,
        "count": len(schools),
        "schools": schools,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def neis_get_academy_list(
    region: str,
    district: str,
    subject: Optional[str] = None,
    limit: Optional[int] = 50,
) -> str:
    """NEIS 학원 목록 조회.

    Args:
        region: 교육청 관할 지역 (예: "서울특별시", "경기도")
        district: 행정구역명 (예: "강남구", "분당구", "수원시")
        subject: 키워드 부분일치 필터 (선택, 예: "수학", "영어", "코딩", "피아노").
                 학원명·분야명·교습과정명 어디든 키워드가 포함되면 매칭.
                 NEIS API의 정확한 분야명은 "입시.검정 및 보습", "예능(대)" 등 — 이런 카테고리는 그대로 입력 가능.
        limit: 최대 반환 건수 (기본 50)
    """
    key = _get_neis_key()
    if not key:
        return "오류: NEIS_API_KEY 환경변수가 설정되지 않았습니다."

    edu_code = _get_edu_code(region)
    # ※ NEIS REALM_SC_NM 필터는 정확 매칭만 허용하므로 클라이언트 측 부분일치로 처리
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": edu_code,
        "ADMST_ZONE_NM": district,
    }

    url = f"{NEIS_BASE}/acaInsTiInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("acaInsTiInfo", [{}])[1].get("row", []) if len(data.get("acaInsTiInfo", [])) > 1 else []
    if not rows:
        error_info = data.get("RESULT", {})
        return json.dumps(
            {"error": error_info.get("MESSAGE", "데이터가 없습니다."), "district": district, "subject": subject},
            ensure_ascii=False,
            indent=2,
        )

    # subject 부분일치 필터 (학원명·분야명·교습과정명 어디든)
    if subject:
        kw = subject.strip()
        rows = [
            r for r in rows
            if kw in (r.get("ACA_NM", "") or "")
            or kw in (r.get("REALM_SC_NM", "") or "")
            or kw in (r.get("LE_ORD_NM", "") or "")
        ]

    total_matched = len(rows)
    rows = rows[: (limit or 50)]

    academies = []
    for row in rows:
        academies.append({
            "name": row.get("ACA_NM", ""),
            "subject": row.get("REALM_SC_NM", ""),
            "course_nm": row.get("LE_ORD_NM", ""),
            "school_level": row.get("SCHUL_CRSE_SC_NM", ""),
            "district": row.get("ADMST_ZONE_NM", ""),
            "address": row.get("FA_RDNMA", ""),
            "phone": row.get("ACA_PHNNO", ""),
        })

    result = {
        "region": region,
        "district": district,
        "subject_filter": subject,
        "matched": total_matched,
        "count": len(academies),
        "academies": academies,
    }
    if subject and total_matched == 0:
        result["hint"] = (
            "키워드와 매칭되는 학원이 없습니다. "
            "neis_get_academy_stats로 해당 지역의 분야별 분포를 먼저 확인하세요."
        )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def neis_get_academy_stats(region: str, district: str) -> str:
    """NEIS 학원 분야별 통계 집계.

    Args:
        region: 교육청 관할 지역 (예: "서울특별시", "경기도")
        district: 행정구역명 (예: "강남구", "마포구")
    """
    key = _get_neis_key()
    if not key:
        return "오류: NEIS_API_KEY 환경변수가 설정되지 않았습니다."

    edu_code = _get_edu_code(region)
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": edu_code,
        "ADMST_ZONE_NM": district,
    }

    url = f"{NEIS_BASE}/acaInsTiInfo"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("acaInsTiInfo", [{}])[1].get("row", []) if len(data.get("acaInsTiInfo", [])) > 1 else []
    if not rows:
        error_info = data.get("RESULT", {})
        return json.dumps(
            {"error": error_info.get("MESSAGE", "데이터가 없습니다."), "district": district},
            ensure_ascii=False,
            indent=2,
        )

    subject_counter: dict[str, int] = {}
    for row in rows:
        subj = row.get("REALM_SC_NM", "기타")
        subject_counter[subj] = subject_counter.get(subj, 0) + 1

    total = len(rows)
    by_subject = sorted(
        [
            {
                "subject": subj,
                "count": cnt,
                "ratio_pct": round(cnt / total * 100, 1),
            }
            for subj, cnt in subject_counter.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    result = {
        "region": region,
        "district": district,
        "total_count": total,
        "by_subject": by_subject,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def schoolzone_lookup(address: str) -> str:
    """초등학교 학구도 안내 (학구도 조회 방법 및 관련 도구 안내).

    Args:
        address: 주소 또는 아파트명 (예: "서울시 강남구 대치동", "은마아파트")
    """
    message = (
        f"학구도 조회는 schoolzone.emac.kr에서 주소로 직접 검색하거나, "
        f"NEIS에서 초등학교를 검색 후 해당 학교의 학구를 확인하세요. "
        f"서울시 {address} 근처 초등학교를 찾으려면 neis_get_school_list 도구를 사용해 주변 학교를 검색하세요.\n\n"
        "참고 링크:\n"
        "- 학구도 안내 시스템: https://schoolzone.emac.kr\n"
        "- data.go.kr 학구도 파일: https://www.data.go.kr/data/15021148/fileData.do\n"
        "- NEIS 교육정보 포털: https://www.neis.go.kr\n\n"
        "neis_get_school_list 도구 사용 예시:\n"
        '  region="서울특별시", school_type="초등학교", district="강남구"'
    )

    result = {
        "address": address,
        "guide": message,
        "tools": ["neis_get_school_list", "neis_get_school_detail"],
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
