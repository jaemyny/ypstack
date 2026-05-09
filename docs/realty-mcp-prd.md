---
title: 한국 부동산 데이터 MCP 통합 (stats-realty + kb-price) PRD
status: Phase 1 완료, Phase 2 예정
version: 1.0
authors: 유진아빠(심재민) / Claude Opus 4.7 (1M context)
created: 2026-05-01
last_updated: 2026-05-09
related_paths:
  - /Users/jaemyny/ypstack/stats-realty-mcp
  - /Users/jaemyny/ypstack/kb-price-mcp
git_repo: github.com/jaemyny/ypstack
---

# 한국 부동산 데이터 MCP 통합 PRD

## 0. Executive Summary

ypstack 모노레포 안에 **한국 부동산 데이터를 LLM 이 직접 조회할 수 있는 MCP 인프라**를 구축한 작업의 PRD. Phase 1 에서는 (a) `stats-realty-mcp` 의 KB 공식 통계 도구 확장과 (b) `kb-price-mcp` 의 단지별 KB 시세 신규 구축을 완료했다. Phase 2 는 운영 자동화·확장·캐싱·문서화 영역으로 정의한다.

| | 작업 | 위치 | 상태 |
|---|---|---|---|
| a | stats-realty KB 통계 도구 확장 (18개) | `stats-realty-mcp/server.py` | ✅ 커밋 `0c3be3a` |
| b | kb-price-mcp 신규 (단지별 시세 4개) | `kb-price-mcp/` | ✅ 커밋 `7d6f2f0` |
| c | Round-3 회귀 버그 수정 | 다수 | ✅ 커밋 `81e89b2`, `f01d78c` |
| d | GUI/CLI 양쪽에서 검증 | — | ✅ 잠실엘스로 4개 도구 호출 성공 |

---

## 1. Background

### 1.1 동기

- 부동산 의사결정(매수·전세·시세 비교)에 필요한 한국 공공·KB 데이터가 산재해 있음
- Claude Code 채팅창에서 "잠실엘스 시세는?" 같은 자연어 질의로 즉답을 얻고 싶음
- 은행 대출 기준이 되는 **KB 시세**는 공식 OpenAPI 가 없어 별도 접근 필요

### 1.2 사전 자산 (Phase 0)

- `stats-realty-mcp` 에 KOSIS·ECOS·RTMS 통합 9개 도구 이미 존재
- `~/Desktop/work/proptech_realty_data/realty_mcp_server.py` (827줄) 에 초기 프로토타입
- `PublicDataReader.Kbland` 라이브러리로 KB 공식 통계 일부 조회 가능

### 1.3 해결할 문제

| # | 문제 | Phase 1 해결 방식 |
|---|---|---|
| P1 | KB 공식 통계가 4종(매매지수·전세지수·HAI·PIR)만 노출, 18종 라이브러리 함수 미활용 | `stats-realty-mcp` 에 14개 추가 노출 |
| P2 | 단지별 KB 시세(대출 기준가) 조회 불가 | HAR 분석 → `kb-price-mcp` 신규 구축 |
| P3 | 옛 폴더와 ypstack 모노레포가 분리되어 정본 위치 혼란 | 옛 폴더 삭제, `~/.claude/projects/-Users-jaemyny-ypstack/memory/` 갱신 |

---

## 2. Goals / Non-Goals

### Goals (Phase 1)

- ✅ KB 월간/주간 시계열 엑셀의 통계 지표를 MCP 도구로 노출 (라이브러리 기반)
- ✅ 단지별 KB 시세 4종 도구 (검색·기본·현재가·시계열)
- ✅ Claude Code GUI 와 CLI 양쪽에서 동일하게 사용 가능
- ✅ 의존성 키 0개로 동작 (api.kbland.kr 비공식 GET 만 사용)

### Non-Goals (Phase 1)

- ❌ KB 매물 호가 리스트 조회 (개별 매물 아님, 단지·평형 단위까지)
- ❌ 자동화된 정기 크롤링·DB 적재 (개인용·on-demand 만)
- ❌ 인증/세션 처리 (비로그인 가능 엔드포인트만 사용)
- ❌ KB 외 부동산 플랫폼(네이버부동산, 호갱노노 등) 통합

---

## 3. Phase 1 — 완료된 작업

### 3.1 작업 a: stats-realty-mcp KB 통계 도구 확장

**커밋:** `0c3be3a feat(stats-realty): KB 월간/주간 시계열 통계 도구 확장`

**기존:** `kb_get_price_stats` 1개 도구 (4종 분기) — DEPRECATED 처리

**신규 (18개, ✅ 16개 작동 / ❌ 2개 KB 차단):**

| # | 도구 | 엑셀 시트 매핑 | 상태 |
|---|---|---|---|
| 1 | `kb_get_price_index` | 월간 1~8, 주간 3~4 | ❌ KB 서버 차단 (`f01d78c`) |
| 2 | `kb_get_price_index_change_rate` | 주간 1~2 (증감률) | ✅ |
| 3 | `kb_get_price_index_by_area` | 월간 39~40 (전용면적별) | ✅ |
| 4 | `kb_get_average_price` | 월간 41~42 | ✅ |
| 5 | `kb_get_average_price_by_area` | 월간 32~38, 55~58 | ✅ |
| 6 | `kb_get_average_price_by_quintile` | 월간 51~54 (5분위) | ✅ |
| 7 | `kb_get_average_price_per_squaremeter` | 월간 45~50 (㎡당) | ✅ |
| 8 | `kb_get_median_price` | 월간 43~44 (중위) | ✅ |
| 9 | `kb_get_wolse_index` | 월간 9 | ✅ |
| 10 | `kb_get_pir` | 월간 11~12 | ✅ |
| 11 | `kb_get_mortgage_loan_pir` | 월간 13 | ✅ |
| 12 | `kb_get_hai` | 월간 14 | ✅ |
| 13 | `kb_get_hoi` | 월간 15 | ✅ |
| 14 | `kb_get_lead50` | 월간 16 (선도50) | ✅ |
| 15 | `kb_get_market_trend` | 월간 21~26, 주간 5~8 | ✅ |
| 16 | `kb_get_jeonse_price_ratio` | 월간 27~30 | ✅ |
| 17 | `kb_get_jeonwolse_conversion_rate` | 월간 59 | ✅ |
| 18 | `kb_get_price_stats` (legacy) | — | ❌ DEPRECATED |

**기술 스택:**
- `PublicDataReader.Kbland` (API 키 불필요)
- 한글 파라미터(`매매전세코드`, `월간주간구분코드` 등)를 영문 enum 으로 래핑
- 응답을 `pandas.to_dict(orient='records')` JSON 으로 정규화

**제약 발견 (`f01d78c` 커밋 시점):**
- `Kbland().get_price_index()` 가 `RemoteDisconnected` 발생 → KB 서버측 IP/UA 차단 추정
- 코드 수정 무관, 라이브러리도 동일 증상 → 우회 불가
- 따라서 #1, #18 은 deprecation 메시지 반환으로 전환
- **시장 동향이 필요하면 #2 (증감률) 또는 #14 (선도50) 사용 권장**

### 3.2 작업 b: kb-price-mcp 신규 구축

**커밋:** `7d6f2f0 feat(kb-price-mcp): KB부동산 단지별 시세 MCP 신규 추가`

**디렉토리 구조:**
```
kb-price-mcp/
├── server.py          # FastMCP 서버 + @mcp.tool 정의 4개
├── kb_client.py       # httpx 래퍼 (헤더, rate limit, 재시도)
├── requirements.txt   # httpx, mcp[cli], pydantic, python-dotenv
├── .env.example       # KB_USER_AGENT (옵션)
├── .gitignore         # .env, *.har, __pycache__
├── README.md
└── tests/
    └── smoke.py       # 잠실엘스 4개 도구 회귀 테스트
```

**도구 (4개, 모두 read-only):**

| 도구 | 시그니처 | 호출 엔드포인트 |
|---|---|---|
| `kb_search_complex` | `(keyword, limit=10)` | `/land-complex/serch/intgraSerch` |
| `kb_get_complex_basic` | `(complex_no)` | `/land-complex/complex/main` + `/land-complex/complex/typInfo` |
| `kb_get_complex_price` | `(complex_no, area_no=None)` | `/land-price/price/BasePrcInfoNew` (평형 미지정 시 전 평형 fan-out) |
| `kb_get_complex_price_history` | `(complex_no, area_no, base_year=None, years=3)` | `/land-price/price/WholQuotList` (연도별 fan-out) |

**HAR 분석 워크플로 (재현 가능):**
1. Chrome DevTools → Network → Fetch/XHR + Preserve log
2. kbland.kr 에서 단지 검색 → KB시세 탭 → 평형 변경 → 시세 추이 클릭
3. ⬇ Export HAR with sensitive data
4. Python `json.load()` 로 파싱 → `api.kbland.kr` 도메인 path 빈도 분석
5. 응답 키 `매매상한가`, `매매일반거래가`, `시세` 등으로 시세 엔드포인트 식별
6. 5개 핵심 엔드포인트 확정 → 도구 매핑

**필수 헤더:**
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/146 ...",
    "Referer": "https://kbland.kr/",
    "Origin": "https://kbland.kr",
    "Accept": "application/json, text/plain, */*",
}
```
**인증 토큰 불필요.** 한글 파라미터 키는 httpx 가 자동 percent-encode.

**응답 정규화:**
- 한글 키(`매매상한가`) → 영문 키(`trade_high_만원`)
- 수치 단위는 KB 그대로(만원 단위) 유지 + suffix 로 명시
- `dataHeader.resultCode != "10000"` 시 에러 메시지 그대로 반환

**Rate limit 정책 (개인용 매너):**
- 호출 간 `asyncio.sleep(0.3)`
- 5xx/타임아웃 시 1회 재시도, 그 외 즉시 에러 반환

### 3.3 인프라·청소 작업

| 항목 | 결과 |
|---|---|
| `~/.claude/mcp.json` 에 `kb-price` 등록 | ✅ |
| CLI (`~/.claude.json`) 에 등록 | ✅ |
| GUI 재시작 후 도구 인식 | ✅ (커넥터 메뉴 UI 표시 누락은 cosmetic 이슈) |
| 옛 `~/Desktop/work/proptech_realty_data/` 삭제 | ✅ |
| `~/.claude/projects/-Users-jaemyny-ypstack/memory/` 갱신 | ✅ |
| Round-3 회귀 버그 수정 (Pydantic·KOSIS·NEIS·ECOS·KB·DART) | ✅ `81e89b2` |
| ECOS 환율/금리 stat_code 매핑 정정 + RATE_ITEM_MAP 추가 | ✅ `f01d78c` |
| `origin/main` 푸시 | ✅ |

### 3.4 검증 결과 (잠실엘스, complex_no=15617, area_no=63146, 2026-05-09 기준)

**현재 시세 (33평 C타입, 시세기준 2026-05-08):**

| 구분 | 상위 | 일반 | 평균 | 하위 | 변동 |
|---|---:|---:|---:|---:|---:|
| 매매 | 33.75억 | 32.75억 | 32.67억 | 31.5억 | 보합 |
| 전세 | 13억 | 12.25억 | 12.25억 | 11.5억 | +2,500만 |
| 월세 | 보증금 1억 / 월 410~450 | | | | |

**시계열 (17개월, 매매 일반거래가):**
- 2025-01: 26.25억 → 2025-12: 33.5억 (**+7.25억, +27.6%**)
- 2026-01~03: 33.5억 정점 후 32.75억 보합 진입

**전 평형 평형별 세대 수:**
- 25평(59㎡) 1,150세대
- 33평 A(84.88㎡) 548 / B(84.97㎡) 556 / C(84.8㎡) 2,938
- 45평(119.93㎡) 486

→ 모든 도구 200 OK, 데이터 정합성 검증 완료.

---

## 4. 기술 아키텍처

### 4.1 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│              Claude Code (GUI / CLI)                    │
│                  │                                      │
│                  ▼                                      │
│           ~/.claude/mcp.json                            │
│           ~/.claude.json                                │
└─────────┬─────────────────────────┬─────────────────────┘
          │                         │
          ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│ stats-realty-mcp     │  │ kb-price-mcp         │
│  (FastMCP, stdio)    │  │  (FastMCP, stdio)    │
│                      │  │                      │
│ - RTMS 실거래        │  │ - 단지 검색          │
│ - 부동산원 가격지수  │  │ - 단지 기본정보      │
│ - KB 통계 16종       │  │ - KB 시세 (현재)     │
│ - KOSIS/ECOS 통합    │  │ - KB 시세 (시계열)   │
└─────────┬────────────┘  └──────────┬───────────┘
          │                          │
          ▼                          ▼
┌──────────────────────┐  ┌──────────────────────┐
│ PublicDataReader     │  │ httpx (직접 호출)    │
│  .Kbland             │  │                      │
│ KOSIS·ECOS·RTMS API  │  │ api.kbland.kr        │
│  (공식, 키 필요)     │  │  (비공식, 키 불필요) │
└──────────────────────┘  └──────────────────────┘
```

### 4.2 의존성

**stats-realty-mcp:**
```
mcp[cli], httpx, pydantic, python-dotenv,
PublicDataReader (KB Kbland·RTMS·KOSIS),
pandas (DataFrame → JSON)
```

**kb-price-mcp:**
```
mcp[cli], httpx, pydantic, python-dotenv
(외부 라이브러리 0, 자체 구현)
```

### 4.3 환경 변수

| 변수 | 위치 | 필요 |
|---|---|---|
| `DATA_GO_KR_KEY` | stats-realty | RTMS 실거래 |
| `REB_API_KEY` | stats-realty | 부동산원 가격지수 |
| `KOSIS_API_KEY` | stats-realty, stats-finance | KOSIS 통계 |
| `ECOS_API_KEY` | stats-finance | 한국은행 |
| `KB_USER_AGENT` | kb-price (선택) | UA 오버라이드 |

모두 `~/.claude/mcp.json` 의 `env` 블록에 등록.

---

## 5. Phase 2 — 예정 작업

### 5.1 단기 (1~2 세션 안에)

#### 5.1.1 GUI/CLI MCP 동기화 스크립트
- **문제:** 새 MCP 추가 시 `~/.claude/mcp.json` (GUI) + `~/.claude.json` (CLI) 양쪽에 따로 등록 필요
- **해결:** `~/ypstack/scripts/sync-mcp-config.sh` 작성
- **구체:** GUI 의 mcp.json 을 정본으로 보고, `claude mcp add-json` 로 CLI 에 자동 등록
- **목표:** 새 MCP 만들 때마다 양쪽 등록 누락 0건

#### 5.1.2 smoke 테스트 자동화
- **문제:** kb-price 가 비공식 API 라 KB 가 스키마 바꾸면 silent break
- **해결:** GitHub Actions 또는 pre-commit hook 으로 회귀 검증
- **구체:**
  - `pytest tests/smoke.py` 잠실엘스·은마 2개 단지로 4개 도구 호출
  - 핵심 응답 키(`trade_high_만원`, `complex_no` 등) assertion
  - 깨지면 알림(slack/email)
- **목표:** KB 스키마 변경을 24시간 안에 감지

#### 5.1.3 엔드포인트 명세 문서
- **위치:** `kb-price-mcp/docs/ENDPOINTS.md`
- **내용:**
  - 우리가 HAR 분석으로 확정한 5개 엔드포인트 명세
  - 한글 응답 키 ↔ 영문 도구 출력 키 전체 매핑표
  - HAR 재캡처 워크플로 (다음에 KB 가 바꿨을 때 어디부터 봐야 하는지)
- **목표:** 다음 사람(또는 미래의 본인)이 30분 안에 진단 가능

### 5.2 중기 (1주~1달)

#### 5.2.1 kb-price-mcp 확장
- **현재:** 4개 도구 (검색·기본·현재가·시계열)
- **HAR 자산:** 53개 고유 엔드포인트 가능성 발견 (단지별 학교, 인근시설, 세금 추정, 매물 카운트, 분양정보 등)
- **우선순위 후보:**
  1. `kb_get_complex_schools` — 학군(초·중·고)
  2. `kb_get_complex_facilities` — 인근 편의시설(지하철·상권 거리)
  3. `kb_get_complex_tax_estimate` — 보유세·취득세 시뮬레이션
  4. `kb_get_complex_listings_count` — 매물 수 추이(매매·전세·월세)
- **목표:** "잠실엘스 학군은?" 같은 질의도 단일 도구로 응답

#### 5.2.2 통합 워크플로 도구 `analyze_complex`
- **문제:** 단지 분석 시 매번 4~5개 도구 따로 호출
- **해결:** `stats-realty + kb-price` 합성 도구 (어느 MCP 에 둘지 결정 필요)
- **시그니처:**
  ```
  analyze_complex(name: str) -> {
    검색: kb_search_complex,
    기본: kb_get_complex_basic,
    KB시세: kb_get_complex_price,
    실거래: rtms_get_apt_trade(최근 6개월),
    KB지수: kb_get_lead50(해당 시군구, 최근 12개월),
    HAI: kb_get_hai(해당 광역시도, 최근 12개월),
  }
  ```
- **목표:** 단일 호출로 단지 분석 풀세트

#### 5.2.3 개인용 SQLite 캐시
- **문제:** KB API 가끔 느림 + 동일 단지 반복 조회
- **해결:** `~/.cache/kb-price/cache.db`
- **TTL:**
  - 단지 메타: 7일
  - 시세 (현재): 1일
  - 시계열 (과거): 30일 (변하지 않음)
- **bypass 옵션:** `force_refresh=True` 파라미터
- **목표:** 동일 단지 재조회 시 즉답, KB 부담 ↓

### 5.3 위생 (시간 날 때)

#### 5.3.1 deprecated 도구 제거
- `stats-realty-mcp` 의 `kb_get_price_stats` (legacy) 와 `kb_get_price_index` (KB 차단)
- 다음 마이너 릴리스에 코드까지 제거 (현재는 메시지만 반환)

#### 5.3.2 README 보강
- `kb-price-mcp/README.md` 현재 2.5KB → 사용 예시 5개 추가
- 잠실엘스로 검색→평형 선택→시세→시계열 e2e 예시
- KB API 차단 시 대응(HAR 재캡처) 가이드 포함

#### 5.3.3 버전 관리 도입
- 두 MCP 모두 `__version__ = "0.1.0"` 추가
- 도구 응답 메타에 서버 버전 포함 → 디버깅 시 추적 용이
- `tools/list` 응답의 server info 에도 버전 노출

### 5.4 보류 항목 (Phase 3+ 가능성)

| 항목 | 이유 |
|---|---|
| 다른 부동산 플랫폼 통합 (네이버, 호갱노노) | KB 시세가 대출 기준 — 우선순위 낮음 |
| 자동 정기 크롤링 | 개인용·on-demand 로 충분, 부담 ↑ |
| 매물 호가 리스트 | KB API 노출되지만 ToS 회색지대 더 짙음 |
| 웹 UI 대시보드 | LLM 자연어 인터페이스가 더 자연스러움 |

---

## 6. 운영·유지보수 가이드

### 6.1 새 MCP 추가 시 체크리스트

- [ ] `~/ypstack/<new-mcp>/server.py` 작성
- [ ] `~/.claude/mcp.json` 에 등록 (절대경로)
- [ ] `claude mcp add-json` 으로 CLI 도 등록
- [ ] Claude Code 완전 재시작 (⌘+Q → 재실행)
- [ ] 잠실엘스(또는 도메인별 표준 케이스)로 smoke 테스트
- [ ] `~/.claude/projects/-Users-jaemyny-ypstack/memory/project_realty_mcp.md` 갱신
- [ ] git commit + push

### 6.2 KB API 가 깨졌을 때 (예상 시나리오)

**증상:** kb-price 호출 시 401/403 또는 응답 스키마 불일치

**진단 순서:**
1. `tests/smoke.py` 실행 → 어느 도구·엔드포인트가 깨졌는지 확인
2. Chrome 으로 kbland.kr 직접 열어서 같은 단지 페이지 진입 (사람 눈으로 동작 확인)
3. 동작하면 → 봇 차단(UA·Referer·쿠키) 의심 → kb_client.py 헤더 갱신
4. 사람도 안 보이면 → KB 측 점검/스키마 변경 → HAR 재캡처
5. HAR 재캡처:
   - DevTools → Network → Fetch/XHR + Preserve log
   - 검색→단지진입→평형변경→시세추이 시나리오 재수행
   - Export HAR with sensitive data
   - Python 으로 path 빈도 분석 → 변경된 엔드포인트 식별
   - server.py / kb_client.py 매핑 갱신

### 6.3 KB 통계 API 차단 (이미 발생) 대응

`PublicDataReader.Kbland().get_price_index()` 의 RemoteDisconnected 는 KB 서버측 차단으로 코드 수정 무관. 시장지수가 필요하면 다음 작동 도구 사용:

- `kb_get_price_index_change_rate` (증감률)
- `kb_get_lead50` (선도50 절대지수)
- `kb_get_price_index_by_area` (면적별 지수)
- `kb_get_average_price` (평균가격)

KB 가 향후 차단을 풀면 자동 복구되므로 코드 변경 불필요.

---

## 7. References

### 7.1 관련 커밋

| 해시 | 메시지 |
|---|---|
| `0c3be3a` | feat(stats-realty): KB 월간/주간 시계열 통계 도구 확장 |
| `7d6f2f0` | feat(kb-price-mcp): KB부동산 단지별 시세 MCP 신규 추가 |
| `81e89b2` | fix: Round-3 critical bugs (Pydantic·KOSIS·NEIS·ECOS·KB·DART) |
| `f01d78c` | fix: ECOS 731Y003 매핑 정정 + KB price_index 외부 API 차단 deprecated 처리 |

### 7.2 외부 참조

- KB부동산: https://kbland.kr (단지·시세)
- KB 월간/주간 시계열: KB부동산 통계 다운로드 페이지 (Excel)
- PublicDataReader 문서: https://wikidocs.net/330015
- KOSIS OpenAPI: https://kosis.kr/openapi
- 한국은행 ECOS: https://ecos.bok.or.kr
- 국토부 RTMS: https://www.data.go.kr (아파트매매 실거래가 상세)
- 한국부동산원 R-ONE: https://www.reb.or.kr/r-one

### 7.3 메모리 위치

- `~/.claude/projects/-Users-jaemyny-ypstack/memory/MEMORY.md`
- `~/.claude/projects/-Users-jaemyny-ypstack/memory/project_realty_mcp.md`

### 7.4 주요 검증 케이스

| 단지 | complex_no | 대표 area_no | 비고 |
|---|---|---|---|
| 잠실엘스 | 15617 | 63146 (33평 C) | Phase 1 검증 표준 단지 |
| 은마아파트 | (HAR 시 캡처됨) | — | Phase 2 회귀 테스트 후보 |

---

## 8. 변경 이력

| 날짜 | 버전 | 변경 |
|---|---|---|
| 2026-05-01 | 0.1 | Phase 1 작업 a/b 시작, kbland.kr HAR 캡처 |
| 2026-05-01 | 0.5 | 작업 a/b 구현 완료, 커밋 푸시 |
| 2026-05-09 | 0.9 | Round-3 회귀 버그 수정, GUI/CLI 검증, 옛 폴더 정리, 메모리 갱신 |
| 2026-05-09 | 1.0 | **Phase 1 완료, PRD 문서화** |

---

## 9. 다음 세션 시작 시 할 일

본 PRD 1.0 시점에서 Phase 1 은 완전히 종료. 다음 세션은 CLI 환경에서 Phase 2 의 **5.1.1 (MCP 동기화 스크립트)** 또는 **5.1.2 (smoke 테스트 자동화)** 부터 진행하는 것을 권장.

```bash
cd /Users/jaemyny/ypstack && claude
# 첫 메시지:
# "docs/realty-mcp-prd.md 의 Phase 2 §5.1.1 부터 진행해줘"
```
