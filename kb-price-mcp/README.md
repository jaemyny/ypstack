# kb-price-mcp

개인용 KB부동산 **단지 시세** MCP 서버. `api.kbland.kr` 비공식 엔드포인트를
`httpx`로 래핑합니다.

> ⚠️ ToS: kbland.kr의 비공식 내부 API를 호출합니다. **개인용 사용에 한정**하며,
> 호출 간격 0.3초 매너 호출 / 5xx 1회 재시도만 적용합니다. 상업적·대량 호출 금지.

## 설치

```bash
cd /Users/jaemyny/ypstack/kb-price-mcp
/opt/homebrew/bin/python3.11 -m pip install -r requirements.txt
```

## 도구 (4개, 모두 read-only)

### 1. `kb_search_complex(keyword, limit=10)`
키워드로 단지 검색. `complex_no` 와 `rep_area_no` 를 얻습니다.

### 2. `kb_get_complex_basic(complex_no)`
단지 기본 메타 + **평형 목록** (각 평형의 `area_no`, 공급/전용면적, 평수, 세대수,
방수, 욕실수 등). 내부적으로 `/complex/main` + `/complex/typInfo` 두 번 호출.

### 3. `kb_get_complex_price(complex_no, area_no=None)`
KB 시세 스냅샷. `area_no` 미지정 시 단지의 모든 평형을 순차 조회합니다.
한 평형이라도 연결구분(일반/저층/탑층)별로 row 가 분리됩니다.

반환 필드 (만원 단위):
- 매매 상한/일반/평균/하한 + 매매변동금액
- 전세 상한/일반/평균/하한 + 전세변동금액
- 월세 보증금 / 월임대 최저·최고 / 월세 평균
- 매물 평균가 (매매/전세/월세 보증금/월세)
- 매매·전세·월세 건수
- `price_date` (시세기준년월일, YYYYMMDD)

### 4. `kb_get_complex_price_history(complex_no, area_no, base_year=None, years=3)`
KB 시세 시계열 (월별). `base_year` 미지정 시 올해부터 거꾸로 `years` 년치를
모아 `year_month` ASC 로 반환합니다.

## 스모크 테스트

```bash
/opt/homebrew/bin/python3.11 tests/smoke.py
```

잠실엘스(15617) → 평형 5개 시세 → 33평C(63146) 2년치 시계열까지 검증.

## MCP 등록

`~/.claude/mcp.json` 에 다음 항목 추가:

```json
"kb-price": {
  "command": "/opt/homebrew/bin/python3.11",
  "args": ["/Users/jaemyny/ypstack/kb-price-mcp/server.py"]
}
```

추가 후 Claude Code 를 재시작하세요.

## 환경변수 (모두 선택)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `KB_USER_AGENT` | Chrome 146 (HAR 캡처값) | UA 오버라이드 |

## 한글 키 주의

`api.kbland.kr` 은 **요청 파라미터 키와 응답 JSON 키가 모두 한글** 입니다.
`httpx` 가 자동으로 percent-encode 하므로 코드에서는 그대로 한글 dict 키를 사용합니다.
