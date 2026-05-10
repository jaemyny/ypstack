---
title: 한국 부동산 MCP 통합 (stats-realty 확장 + kb-price 신규) PRD
status: Phase 1 완료, Phase 2 예정
version: 1.1
authors: 유진아빠(심재민) / Claude Opus 4.7 (1M context)
created: 2026-05-01
last_updated: 2026-05-10
scope_subdirs:
  - stats-realty-mcp
  - kb-price-mcp
related_paths:
  - /Users/jaemyny/ypstack/stats-realty-mcp
  - /Users/jaemyny/ypstack/kb-price-mcp
git_repo: github.com/jaemyny/ypstack
---

# 한국 부동산 MCP 통합 PRD

## 0. 이 문서의 범위

이 PRD 는 **단일 채팅 쓰레드에서 진행한 두 작업만** 다룬다. ypstack 모노레포에는 이 문서 외에도 다른 세션에서 병렬로 진행 중인 작업들이 있으나(stats-finance ECOS 매핑 정정, Round-3 회귀 버그 수정 등), 그것들은 이 PRD 의 범위가 아니다.

| | 작업 | 위치 | 상태 |
|---|---|---|---|
| **(a)** | stats-realty-mcp 의 KB 통계 도구 확장 | `stats-realty-mcp/server.py` | ✅ 커밋 `0c3be3a` |
| **(b)** | kb-price-mcp 신규 (단지별 KB 시세) | `kb-price-mcp/` | ✅ 커밋 `7d6f2f0` |

**참고:** §6 운영가이드의 **§6.4 모노레포 병렬 세션 자동화** 는 이 PRD 외 영역에서 발생하는 노이즈를 격리하기 위해 도입한 인프라이며, Phase 1 완료 직후 추가됐다.

---

## 1. Background

### 1.1 동기

- KB 부동산이 제공하는 데이터(공식 통계 + 단지별 KB시세) 를 Claude Code 채팅창에서 자연어로 즉답
- 기존 `stats-realty-mcp` 의 KB 도구가 4종에 그쳐 KB 가 제공하는 18종 통계 라이브러리 함수의 대부분이 미활용
- 은행 대출 기준이 되는 **KB 시세(개별 단지·평형)** 는 공식 OpenAPI 가 없어 별도 접근 필요

### 1.2 사전 자산 (Phase 0)

- `stats-realty-mcp` 에 KOSIS·ECOS·RTMS 통합 9개 도구 + KB 통계 4종 (`kb_get_price_stats` 1개 도구의 stat_type 분기) 이미 존재
- `PublicDataReader.Kbland` 라이브러리로 KB 공식 통계 일부 조회 가능 (API 키 불필요)
- HAR 캡처·분석 워크플로 (Chrome DevTools 기반)

### 1.3 해결할 문제

| # | 문제 | 해결 방식 |
|---|---|---|
| **P1** | KB 공식 통계가 4종만 노출, 18종 라이브러리 함수 미활용 | **(a)** stats-realty-mcp 에 14개 신설 |
| **P2** | 단지별 KB 시세 조회 불가 | **(b)** kb-price-mcp 신규 구축 (HAR 분석으로 비공식 엔드포인트 5개 확정) |

---

## 2. Goals / Non-Goals

### Goals (Phase 1)

- ✅ KB 월간/주간 시계열 엑셀의 통계 지표를 MCP 도구로 노출 (라이브러리 기반)
- ✅ 단지별 KB 시세 4종 도구 (검색·기본·현재가·시계열)
- ✅ Claude Code GUI / CLI 양쪽에서 동일하게 사용 가능
- ✅ 의존성 키 0개 동작 (api.kbland.kr 비공식 GET 만 사용)

### Non-Goals (Phase 1)

- ❌ KB 매물 호가 리스트 조회 (단지·평형 단위까지)
- ❌ 자동화된 정기 크롤링·DB 적재 (개인용·on-demand 만)
- ❌ 인증/세션 처리 (비로그인 가능 엔드포인트만 사용)
- ❌ KB 외 부동산 플랫폼(네이버부동산, 호갱노노 등) 통합

---

## 3. Phase 1 — 완료된 작업

### 3.1 작업 (a): stats-realty-mcp KB 통계 도구 확장

**커밋:** `0c3be3a feat(stats-realty): KB 월간/주간 시계열 통계 도구 확장`

**기존:** `kb_get_price_stats` 1개 도구 (4종 분기) — DEPRECATED 처리

**신규 (총 18개 등록 / ✅ 16개 작동 / ❌ 2개 KB 차단):**

| # | 도구 | KB 엑셀 시트 매핑 | 상태 |
|---|---|---|---|
| 1 | `kb_get_price_index` | 월간 1~8, 주간 3~4 | ❌ KB 서버 차단 |
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
- 한글 파라미터(`매매전세코드`, `월간주간구분코드` 등) 를 영문 enum 으로 래핑
- 응답을 `pandas.to_dict(orient='records')` JSON 으로 정규화

**제약 발견 (작업 a 완료 후):**

- `Kbland().get_price_index()` 가 `RemoteDisconnected` 발생 → KB 서버측 IP/UA 차단 추정
- 라이브러리/코드 수정 무관, 우회 불가
- → #1, #18 은 deprecation 메시지 반환으로 전환 (다른 세션이 별도 커밋으로 처리)
- **시장 동향이 필요하면 #2 (증감률) 또는 #14 (선도50) 사용**

### 3.2 작업 (b): kb-price-mcp 신규 구축

**커밋:** `7d6f2f0 feat(kb-price-mcp): KB부동산 단지별 시세 MCP 신규 추가`

**디렉토리 구조:**

```
kb-price-mcp/
├── server.py          # FastMCP 서버 + @mcp.tool 정의 4개
├── kb_client.py       # httpx 래퍼 (헤더, rate limit, 재시도)
├── requirements.txt   # httpx, mcp[cli], pydantic, python-dotenv
├── .env.example       # KB_USER_AGENT (옵션)
├── .gitignore
├── README.md
└── tests/
    └── smoke.py       # 잠실엘스 4개 도구 회귀 테스트
```

**도구 (4개, 모두 read-only):**

| 도구 | 시그니처 | 호출 엔드포인트 |
|---|---|---|
| `kb_search_complex` | `(keyword, limit=10)` | `/land-complex/serch/intgraSerch` |
| `kb_get_complex_basic` | `(complex_no)` | `/land-complex/complex/main` + `/typInfo` |
| `kb_get_complex_price` | `(complex_no, area_no=None)` | `/land-price/price/BasePrcInfoNew` (평형 미지정 시 fan-out) |
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
    "User-Agent": "Mozilla/5.0 ... Chrome/146 ...",
    "Referer":    "https://kbland.kr/",
    "Origin":     "https://kbland.kr",
    "Accept":     "application/json, text/plain, */*",
}
```

**인증 토큰 불필요.** 한글 파라미터 키는 httpx 가 자동 percent-encode.

**응답 정규화:**

- 한글 키(`매매상한가`) → 영문 키(`trade_high_만원`)
- 수치 단위는 KB 그대로(만원 단위) 유지 + suffix 명시
- `dataHeader.resultCode != "10000"` 시 에러 메시지 그대로 반환

**Rate limit 정책 (개인용 매너):**

- 호출 간 `asyncio.sleep(0.3)`
- 5xx/타임아웃 시 1회 재시도, 그 외 즉시 에러

### 3.3 검증 결과 (잠실엘스, complex_no=15617, area_no=63146)

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

- 25평 1,150 / 33평 A 548 / 33평 B 556 / 33평 C 2,938 / 45평 486

→ **GUI / CLI 양쪽에서 4개 도구 모두 200 OK 검증 완료.**

### 3.4 인프라·청소 작업

| 항목 | 결과 |
|---|---|
| `~/.claude/mcp.json` 에 `kb-price` 등록 | ✅ |
| CLI (`~/.claude.json`) 에 등록 | ✅ |
| GUI 재시작 후 도구 인식 | ✅ (커넥터 메뉴 UI 누락은 cosmetic) |
| 옛 `~/Desktop/work/proptech_realty_data/` 삭제 | ✅ |
| `~/.claude/projects/-Users-jaemyny-ypstack/memory/` 갱신 | ✅ |
| `origin/main` 푸시 | ✅ |

---

## 4. 기술 아키텍처

### 4.1 시스템 다이어그램

```
┌──────────────────────────────────────────────┐
│      Claude Code (GUI / CLI)                 │
│             │                                │
│             ▼                                │
│      ~/.claude/mcp.json                      │
│      ~/.claude.json                          │
└─────────┬────────────────┬───────────────────┘
          │                │
          ▼                ▼
┌────────────────┐  ┌────────────────┐
│ stats-realty   │  │ kb-price-mcp   │
│  -mcp          │  │  (FastMCP)     │
│  (FastMCP)     │  │                │
│                │  │ - 단지 검색    │
│ - RTMS 실거래  │  │ - 단지 기본    │
│ - REB 가격지수 │  │ - KB시세 현재  │
│ - KB 통계 16종 │  │ - KB시세 시계열│
│ - KOSIS/ECOS   │  │                │
└────────┬───────┘  └────────┬───────┘
         │                   │
         ▼                   ▼
┌────────────────┐  ┌────────────────┐
│PublicDataReader│  │ httpx 직접 호출│
│ .Kbland        │  │ api.kbland.kr  │
│ KOSIS·ECOS·RTMS│  │  (비공식,      │
│  (공식, 키 필요)│  │   키 불필요)   │
└────────────────┘  └────────────────┘
```

### 4.2 의존성

| MCP | 라이브러리 |
|---|---|
| stats-realty-mcp | `mcp[cli]`, `httpx`, `pydantic`, `python-dotenv`, `PublicDataReader`, `pandas` |
| kb-price-mcp | `mcp[cli]`, `httpx`, `pydantic`, `python-dotenv` (외부 라이브러리 0) |

### 4.3 환경 변수

| 변수 | MCP | 필요 |
|---|---|---|
| `DATA_GO_KR_KEY` | stats-realty | RTMS 실거래 |
| `REB_API_KEY` | stats-realty | 부동산원 가격지수 |
| `KOSIS_API_KEY` | stats-realty | KOSIS 통계 |
| `KB_USER_AGENT` | kb-price (선택) | UA 오버라이드 |

모두 `~/.claude/mcp.json` 의 `env` 블록에 등록.

---

## 5. Phase 2 — 예정 작업

### 5.1 단기 (1~2 세션 안에)

#### 5.1.1 GUI/CLI MCP 동기화 스크립트

- **문제:** 새 MCP 추가 시 `~/.claude/mcp.json` (GUI) + `~/.claude.json` (CLI) 양쪽 등록 필요
- **해결:** `scripts/sync-mcp-config.sh` 작성 — GUI 정본을 CLI 로 전파

#### 5.1.2 smoke 테스트 자동화

- **문제:** kb-price 가 비공식 API 라 KB 가 스키마 바꾸면 silent break
- **해결:** GitHub Actions 또는 pre-commit hook 으로 회귀 검증
- **구체:** 잠실엘스·은마 2개 단지 × 4개 도구 호출 + 핵심 응답 키 assertion

#### 5.1.3 엔드포인트 명세 문서

- **위치:** `kb-price-mcp/docs/ENDPOINTS.md`
- **내용:** 5개 엔드포인트 명세 / 한글 ↔ 영문 키 매핑표 / HAR 재캡처 워크플로

### 5.2 중기 (1주~1달)

#### 5.2.1 kb-price-mcp 확장

- HAR 캡처에서 53개 고유 엔드포인트 발견. 우선순위 후보:
  1. `kb_get_complex_schools` — 학군
  2. `kb_get_complex_facilities` — 인근 편의시설
  3. `kb_get_complex_tax_estimate` — 보유세·취득세 시뮬
  4. `kb_get_complex_listings_count` — 매물 수 추이

#### 5.2.2 통합 워크플로 도구 `analyze_complex`

- 단일 호출로 검색 + 기본 + KB시세 + 실거래 + KB지수 + HAI 묶어 응답

#### 5.2.3 개인용 SQLite 캐시

- `~/.cache/kb-price/cache.db`
- TTL: 메타 7일 / 시세 현재 1일 / 시계열 30일

### 5.3 위생

- deprecated 도구 코드 제거 (`kb_get_price_stats`, `kb_get_price_index`)
- README 보강 (사용 예시 5개 추가)
- `__version__` 도입

---

## 6. 운영·유지보수 가이드

### 6.1 새 MCP 추가 체크리스트

- [ ] `yp-session.sh <new-mcp-subdir>` 로 격리 worktree 진입
- [ ] `<subdir>/server.py` 작성 (FastMCP 패턴)
- [ ] `~/.claude/mcp.json` 에 등록 (절대경로)
- [ ] `claude mcp add-json` 으로 CLI 도 등록
- [ ] Claude Code 완전 재시작
- [ ] 도메인별 표준 케이스로 smoke 테스트
- [ ] `~/.claude/projects/-Users-jaemyny-ypstack/memory/project_*.md` 갱신
- [ ] worktree 안에서 `git push -u origin work/<subdir>`
- [ ] main merge 는 사용자 명시 요청 후

### 6.2 KB API 가 깨졌을 때 진단 순서

1. `tests/smoke.py` 실행 → 어느 도구·엔드포인트가 깨졌는지
2. Chrome 으로 kbland.kr 직접 열어 같은 단지 페이지 진입 (사람 눈 확인)
3. 동작하면 → 봇 차단 의심 → `kb_client.py` 헤더(UA·Referer) 갱신
4. 사람도 안 보이면 → KB 점검/스키마 변경 → HAR 재캡처
5. HAR 재캡처 → path 빈도 분석 → server.py / kb_client.py 매핑 갱신

### 6.3 KB 통계 API 차단 (이미 발생) 대응

`Kbland().get_price_index()` 의 RemoteDisconnected 는 KB 서버측 차단으로 코드 수정 무관. 시장지수가 필요하면:

- `kb_get_price_index_change_rate` (증감률)
- `kb_get_lead50` (선도50 절대지수)
- `kb_get_price_index_by_area` (면적별 지수)
- `kb_get_average_price` (평균가격)

KB 가 차단을 풀면 자동 복구.

### 6.4 모노레포 병렬 세션 자동화 ⭐

ypstack 은 단일 모노레포에 여러 MCP / skill 이 공존하므로 여러 세션이 동시에 다른 subdir 를 작업할 수 있다. 이로 인한 실수(다른 세션 변경을 휩쓸어 commit, scope 외 파일 편집)를 방지하기 위해 **3-layer 자동화** 가 적용되어 있다:

#### Layer 1 — `~/ypstack/CLAUDE.md` (자동 컨텍스트 주입)

cwd 가 ypstack 또는 worktree 일 때 자동으로 system prompt 에 합성. 사용자가 따로 지시하지 않아도 Claude 가 모노레포 규칙(scope·git·cross-cutting)을 항상 인지.

#### Layer 2 — `~/ypstack/.claude/settings.json` Hooks (OS 레벨 차단)

```
PreToolUse:
  Edit/Write/NotebookEdit → check-edit-scope.sh
  Bash                    → check-git-safety.sh
```

- `check-edit-scope.sh`: cwd 의 `.yp-session-scope` 읽어 작업 subdir 외 편집 차단 (exit 2)
- `check-git-safety.sh`: `git add . / -A`, `git commit -a / -am` 차단 (exit 2)
- 통과 시 silent (exit 0), cross-cutting 은 경고만 (exit 0 + stderr ℹ️)

#### Layer 3 — `~/ypstack/scripts/yp-session.sh` (워크트리 자동화)

```bash
yp-session.sh kb-price-mcp
# 자동 처리:
#  ① ~/ypstack-wt/kb-price-mcp/ git worktree 생성/재사용
#  ② work/kb-price-mcp 브랜치 분기/재사용
#  ③ .yp-session-scope = "kb-price-mcp" 작성
#  ④ claude --dangerously-skip-permissions 실행
```

worktree 격리로 그 세션의 `git status` 는 자기 worktree 만 보여줌 — 다른 세션 변경이 시야에서 사라짐 (물리적 격리).

#### 작업 흐름 표준 (요약)

```
[새 작업] → yp-session.sh <subdir>
              ↓
       [worktree 격리 세션 진입]
              ↓
       [Claude 가 CLAUDE.md 자동 로드]
              ↓
   [편집·git 위험 명령 hook 으로 차단]
              ↓
        [작업 → 명시적 git add → commit]
              ↓
       [push -u origin work/<subdir>]
              ↓
    [필요 시 사용자 요청으로 main merge]
              ↓
     [yp-session.sh clean <subdir>] (선택)
```

---

## 7. References

### 7.1 이 PRD 가 다루는 커밋

| 해시 | 메시지 | 범위 |
|---|---|---|
| `0c3be3a` | feat(stats-realty): KB 월간/주간 시계열 통계 도구 확장 | 작업 (a) |
| `7d6f2f0` | feat(kb-price-mcp): KB부동산 단지별 시세 MCP 신규 추가 | 작업 (b) |

### 7.2 외부 참조

- KB부동산: https://kbland.kr (단지·시세)
- PublicDataReader: https://wikidocs.net/330015
- KOSIS: https://kosis.kr/openapi
- 한국은행 ECOS: https://ecos.bok.or.kr
- 국토부 RTMS: https://www.data.go.kr
- 한국부동산원 R-ONE: https://www.reb.or.kr/r-one

### 7.3 메모리 위치

- `~/.claude/projects/-Users-jaemyny-ypstack/memory/MEMORY.md`
- `~/.claude/projects/-Users-jaemyny-ypstack/memory/project_realty_mcp.md`

### 7.4 검증 단지

| 단지 | complex_no | 대표 area_no | 비고 |
|---|---|---|---|
| 잠실엘스 | 15617 | 63146 (33평 C) | Phase 1 검증 표준 단지 |

---

## 8. 변경 이력

| 날짜 | 버전 | 변경 |
|---|---|---|
| 2026-05-01 | 0.5 | 작업 (a)/(b) 구현 완료, 커밋 푸시 |
| 2026-05-09 | 1.0 | Phase 1 PRD 초안 (다른 세션 작업 혼재) |
| 2026-05-10 | **1.1** | **PRD 범위 정정 (작업 a/b 한정), §6.4 모노레포 병렬 세션 자동화 추가** |

---

## 9. 다음 세션 시작 시

```bash
# Phase 2 단기 §5.1.1 진행하려면:
~/ypstack/scripts/yp-session.sh scripts
# (cross-cutting 작업이라 scope=scripts 로 진입 후 사용자 명시 허락)

# 또는 부동산 MCP 작업이면:
~/ypstack/scripts/yp-session.sh kb-price-mcp
~/ypstack/scripts/yp-session.sh stats-realty-mcp
```

위 명령으로 진입 시 worktree 격리 + CLAUDE.md 자동 로드 + scope hook 활성 + `--dangerously-skip-permissions` 실행이 한 번에 이뤄진다.
