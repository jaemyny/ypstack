#!/usr/bin/env python3
"""kb-price-mcp: KB부동산 단지 시세 (개인용, api.kbland.kr 비공식).

도구:
- kb_search_complex: 키워드로 단지 검색 → COMPLEX_NO 획득
- kb_get_complex_basic: 단지 기본정보 + 평형 목록(면적일련번호 포함)
- kb_get_complex_price: 평형별 KB 시세 (매매/전세/월세 상한·일반·하한)
- kb_get_complex_price_history: 평형별 KB 시세 시계열 (월별)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from kb_client import get_client

mcp = FastMCP("kb-price")


def _err(msg: str, **extra: Any) -> str:
    out = {"error": msg}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False, indent=2)


def _ok(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 1: 단지 검색
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_search_complex(keyword: str, limit: int = 10) -> str:
    """키워드로 KB부동산 단지를 검색합니다 (아파트만).

    Args:
        keyword: 검색어 (예: "잠실엘스", "송파구 잠실동")
        limit: 최대 반환 건수 (기본 10)
    """
    if not keyword.strip():
        return _err("keyword 가 비어 있습니다.")

    res = await get_client().get_json(
        "/land-complex/serch/intgraSerch",
        {
            "검색설정명": "SRC_HSCM",
            "검색키워드": keyword,
            "출력갯수": limit,
            "페이지설정값": 1,
        },
    )
    if "error" in res:
        return _ok(res)

    # dataBody.data.data.HSCM.data[]
    data = res["data"]
    hscm = (data.get("data") or {}).get("HSCM") or {}
    rows = hscm.get("data") or []

    results = []
    for r in rows:
        results.append({
            "complex_no": r.get("COMPLEX_NO"),
            "name": r.get("HSCM_NM"),
            "name_full": r.get("HSCM_NM_EXT"),
            "address_jibun": r.get("JUSO_ARNO") or r.get("BUBADDR"),
            "address_road": r.get("NEWADDRESS"),
            "law_dong_code": r.get("BUBCODE"),
            "total_households": _to_int(r.get("THS_NUM")),
            "area_range_m2": r.get("SQRMSR_SCOP"),
            "build_ymd": r.get("MVIHS_DATE"),
            "rep_area_no": r.get("RPSNT_SQRMSR_NO"),
            "lat": _to_float(r.get("WGS84_LAT")),
            "lng": _to_float(r.get("WGS84_LNG")),
            "type": r.get("SLND_PERTY_NM"),
        })

    return _ok({
        "keyword": keyword,
        "count": len(results),
        "totcnt": _to_int(hscm.get("totcnt")),
        "results": results,
    })


# ---------------------------------------------------------------------------
# 도구 2: 단지 기본정보 + 평형 목록
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_complex_basic(complex_no: str) -> str:
    """단지 기본정보(메타) + 평형 목록(면적일련번호)을 조회합니다.

    Args:
        complex_no: 단지기본일련번호 (kb_search_complex 의 complex_no)
    """
    if not complex_no:
        return _err("complex_no 가 비어 있습니다.")

    client = get_client()

    main_res = await client.get_json(
        "/land-complex/complex/main",
        {"단지기본일련번호": complex_no},
    )
    typ_res = await client.get_json(
        "/land-complex/complex/typInfo",
        {"단지기본일련번호": complex_no},
    )

    if "error" in main_res:
        return _ok(main_res)

    m = main_res["data"]
    meta = {
        "complex_no": str(m.get("단지기본일련번호") or complex_no),
        "name": m.get("단지명"),
        "type": m.get("매물종별구분명"),
        "address_road": m.get("도로기본주소") or m.get("신주소"),
        "address_jibun": m.get("구주소"),
        "law_dong_code": m.get("법정동코드"),
        "build_ymd": m.get("준공년월일"),
        "build_age_years": m.get("입주년수"),
        "total_households": m.get("총세대수"),
        "general_households": m.get("일반세대수"),
        "rental_households": m.get("임대세대수"),
        "total_buildings": m.get("총동수"),
        "max_floor": m.get("최고층수"),
        "min_floor": m.get("최저층수"),
        "total_parking": m.get("총주차대수"),
        "parking_per_household": m.get("세대당주차대수비율"),
        "heating": m.get("난방방식구분명"),
        "heating_fuel": m.get("난방연료구분명"),
        "builder": m.get("시공사명"),
        "developer": m.get("시행업체명"),
        "floor_area_ratio": m.get("용적률내용"),
        "building_coverage_ratio": m.get("건폐율내용"),
        "elevator": m.get("승강기유무"),
        "rebuilding_yn": m.get("재건축여부"),
        "redevelopment_yn": m.get("재개발여부"),
        "office_phone": m.get("관리사무소전화번호내용"),
        "lat": m.get("wgs84위도"),
        "lng": m.get("wgs84경도"),
        "view_count": m.get("viewCount"),
        "min_supply_area_m2": m.get("최소공급면적"),
        "max_supply_area_m2": m.get("최대공급면적"),
        "rep_area_no": m.get("대표면적일련번호"),
        "rep_supply_area_m2": m.get("대표공급면적"),
        "rep_exclusive_area_m2": m.get("대표전용면적"),
    }

    # 평형 목록은 typInfo 에서
    types = []
    if "error" not in typ_res:
        for t in typ_res["data"] or []:
            types.append({
                "area_no": str(t.get("면적일련번호") or ""),
                "type_name": t.get("주택형타입내용") or "",
                "supply_area_m2": _to_float(t.get("공급면적")),
                "supply_area_pyeong": _to_float(t.get("공급면적평")),
                "exclusive_area_m2": _to_float(t.get("전용면적")),
                "exclusive_area_pyeong": _to_float(t.get("전용면적평")),
                "contract_area_m2": _to_float(t.get("계약면적")),
                "contract_area_pyeong": _to_float(t.get("계약면적평")),
                "households": t.get("세대수"),
                "rooms": t.get("방수"),
                "bathrooms": t.get("욕실수"),
                "exclusive_rate_pct": _to_float(t.get("전용률")),
                "kms_size_code": t.get("KMS평형코드"),
                "trade_count": t.get("매매건수"),
                "jeonse_count": t.get("전세건수"),
                "wolse_count": t.get("월세건수"),
            })
        types.sort(key=lambda x: (x["supply_area_m2"] or 0))

    out = {"meta": meta, "area_types": types}
    if "error" in typ_res:
        out["area_types_error"] = typ_res["error"]
    return _ok(out)


# ---------------------------------------------------------------------------
# 도구 3: 평형별 KB 시세 (현재)
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_complex_price(complex_no: str, area_no: Optional[str] = None) -> str:
    """KB부동산 단지 시세를 조회합니다 (현재 시점).

    area_no 가 주어지면 해당 평형만 조회합니다. None 이면 전 평형을 순차 조회합니다.

    Args:
        complex_no: 단지기본일련번호
        area_no: 면적일련번호 (선택). 미지정 시 전 평형 fan-out.
    """
    if not complex_no:
        return _err("complex_no 가 비어 있습니다.")

    client = get_client()

    if area_no:
        area_nos: list[tuple[str, dict[str, Any]]] = [(str(area_no), {})]
    else:
        # 평형 목록을 typInfo 로 먼저 받음
        typ_res = await client.get_json(
            "/land-complex/complex/typInfo",
            {"단지기본일련번호": complex_no},
        )
        if "error" in typ_res:
            return _ok(typ_res)
        area_nos = []
        for t in typ_res["data"] or []:
            an = str(t.get("면적일련번호") or "")
            if not an:
                continue
            area_nos.append((an, {
                "supply_area_m2": _to_float(t.get("공급면적")),
                "supply_area_pyeong": _to_float(t.get("공급면적평")),
                "exclusive_area_m2": _to_float(t.get("전용면적")),
                "exclusive_area_pyeong": _to_float(t.get("전용면적평")),
                "type_name": t.get("주택형타입내용") or "",
                "households": t.get("세대수"),
            }))

    if not area_nos:
        return _err("평형 목록을 찾지 못했습니다.", complex_no=complex_no)

    out_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for an, hint in area_nos:
        res = await client.get_json(
            "/land-price/price/BasePrcInfoNew",
            {"단지기본일련번호": complex_no, "면적일련번호": an},
        )
        if "error" in res:
            errors.append({"area_no": an, **res})
            continue
        d = res["data"]
        # 시세 배열은 연결구분(일반/저층/탑층 등) 별로 1개씩
        for row in d.get("시세") or []:
            out_rows.append({
                "area_no": str(row.get("면적일련번호") or an),
                "type_name": row.get("주택형타입내용") or hint.get("type_name", ""),
                "connection": row.get("연결구분명"),
                "supply_area_m2": _to_float(row.get("공급면적")) or hint.get("supply_area_m2"),
                "supply_area_pyeong": _to_int(row.get("공급면적평수")) or hint.get("supply_area_pyeong"),
                "exclusive_area_m2": _to_float(row.get("전용면적")) or hint.get("exclusive_area_m2"),
                "exclusive_area_pyeong": _to_int(row.get("전용면적평수")) or hint.get("exclusive_area_pyeong"),
                "price_date": row.get("시세기준년월일"),
                "trade_high_만원": row.get("매매상한가"),
                "trade_general_만원": row.get("매매일반거래가"),
                "trade_avg_만원": row.get("매매평균가"),
                "trade_low_만원": row.get("매매하한가"),
                "trade_change_만원": row.get("매매변동금액"),
                "jeonse_high_만원": row.get("전세상한가"),
                "jeonse_general_만원": row.get("전세일반거래가"),
                "jeonse_avg_만원": row.get("전세평균가"),
                "jeonse_low_만원": row.get("전세하한가"),
                "jeonse_change_만원": row.get("전세변동금액"),
                "wolse_deposit_만원": row.get("월세보증금액"),
                "wolse_min_만원": row.get("월임대최저금액"),
                "wolse_max_만원": row.get("월임대최고금액"),
                "wolse_amount_만원": row.get("월세금액"),
                "listing_jeonse_avg_만원": d.get("매물전세평균가"),
                "listing_trade_avg_만원": d.get("매물매매평균가"),
                "listing_wolse_deposit_avg_만원": d.get("매물월세보증금평균가"),
                "listing_wolse_avg_만원": d.get("매물월세평균가"),
                "trade_count": d.get("매매건수"),
                "jeonse_count": d.get("전세건수"),
                "wolse_count": d.get("월세건수"),
                "is_provided": row.get("시세제공여부") in (1, "1"),
                "no_provide_reason": row.get("시세미제공사유"),
            })

    payload: dict[str, Any] = {
        "complex_no": complex_no,
        "count": len(out_rows),
        "rows": out_rows,
    }
    if errors:
        payload["errors"] = errors
    return _ok(payload)


# ---------------------------------------------------------------------------
# 도구 4: 평형별 KB 시세 시계열
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
async def kb_get_complex_price_history(
    complex_no: str,
    area_no: str,
    base_year: Optional[int] = None,
    years: int = 3,
) -> str:
    """KB부동산 단지 시세 시계열(월별)을 조회합니다.

    base_year 부터 거꾸로 years 년치를 합쳐서 기준년월 ASC 로 반환합니다.

    Args:
        complex_no: 단지기본일련번호
        area_no: 면적일련번호
        base_year: 기준년 (YYYY). 미지정 시 올해.
        years: 몇 년치를 가져올지 (기본 3)
    """
    if not complex_no or not area_no:
        return _err("complex_no, area_no 둘 다 필요합니다.")
    if years < 1 or years > 20:
        return _err("years 는 1~20 사이여야 합니다.")

    if base_year is None:
        base_year = dt.date.today().year

    client = get_client()

    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for y in range(base_year, base_year - years, -1):
        res = await client.get_json(
            "/land-price/price/WholQuotList",
            {"단지기본일련번호": complex_no, "면적일련번호": area_no, "기준년": y},
        )
        if "error" in res:
            errors.append({"year": y, **res})
            continue
        groups = (res["data"] or {}).get("시세") or []
        for g in groups:
            for it in g.get("items") or []:
                items.append({
                    "year_month": it.get("기준년월"),
                    "trade_high_만원": it.get("매매상한가"),
                    "trade_general_만원": it.get("매매일반거래가"),
                    "trade_low_만원": it.get("매매하한가"),
                    "jeonse_high_만원": it.get("전세상한가"),
                    "jeonse_general_만원": it.get("전세일반거래가"),
                    "jeonse_low_만원": it.get("전세하한가"),
                    "wolse_deposit_만원": it.get("월세보증금액"),
                    "wolse_min_만원": it.get("월임대최저금액"),
                    "wolse_max_만원": it.get("월임대최고금액"),
                })

    # 기준년월 ASC 로 정렬, 중복 제거
    seen_ym: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda x: x.get("year_month") or ""):
        ym = it.get("year_month")
        if not ym or ym in seen_ym:
            continue
        seen_ym.add(ym)
        deduped.append(it)

    payload = {
        "complex_no": complex_no,
        "area_no": area_no,
        "base_year": base_year,
        "years": years,
        "count": len(deduped),
        "items": deduped,
    }
    if errors:
        payload["errors"] = errors
    return _ok(payload)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
