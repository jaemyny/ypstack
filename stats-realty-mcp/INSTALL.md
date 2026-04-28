# stats-realty-mcp 설치 가이드

Claude Code에서 자연어로 아파트 실거래·전월세·단지정보·주택인허가·가격지수를 조회하는 MCP 서버입니다.

---

## 제공 도구 (9개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `rtms_get_apt_trade` | 아파트 매매 실거래가 조회 | DATA_GO_KR |
| `rtms_get_apt_rent` | 아파트 전월세 실거래 조회 | DATA_GO_KR |
| `rtms_get_apt_presale_transfer` | 아파트 분양권 전매 조회 | DATA_GO_KR |
| `apt_search_complex` | 아파트 단지 검색 | DATA_GO_KR |
| `apt_get_complex_detail` | 아파트 단지 상세정보 | DATA_GO_KR |
| `molit_get_housing_permit` | 주택건설 인허가 실적 | KOSIS |
| `reb_get_price_index` | 한국부동산원 매매·전세 가격지수 | REB |
| `kb_get_price_stats` | KB부동산 가격통계 (HAI·PIR 포함) | 불필요 |
| `rtms_get_lawd_codes` | 지역 법정동 코드 조회 | 불필요 |

---

## 필요 API 키

### DATA_GO_KR (공공데이터포털) — 실거래·단지 정보
1. [https://www.data.go.kr](https://www.data.go.kr) 접속 후 회원가입
2. "아파트매매실거래자료" 검색 → **국토교통부_아파트매매실거래자료** 활용신청
3. 마이페이지 → 활용신청 내역 → **일반 인증키(Decoding)** 복사

> 하나의 키로 RTMS·단지 API 전체 사용 가능합니다.

### REB (한국부동산원 R-ONE)
1. [https://www.reb.or.kr/r-one/main.do](https://www.reb.or.kr/r-one/main.do) 접속
2. 회원가입 후 **OpenAPI 신청** 메뉴에서 발급

### KOSIS (통계청) — 주택인허가 통계
1. [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp) 접속
2. 회원가입 후 OPEN API 활용신청 → 마이페이지에서 API 키 확인
> KOSIS 키는 Base64 형식입니다. 발급받은 키를 그대로 사용하세요.

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-realty-mcp/setup.sh
```

---

## 수동 설치

### 1. 패키지 설치

```bash
python3 -m pip install "mcp[cli]" httpx pydantic
# KB부동산 통계 사용 시 (선택)
python3 -m pip install PublicDataReader
```

### 2. `~/.claude/mcp.json` 에 추가

```json
{
  "mcpServers": {
    "stats-realty": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-realty-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "여기에_공공데이터포털_키",
        "REB_API_KEY":    "여기에_한국부동산원_키",
        "KOSIS_API_KEY":  "여기에_KOSIS_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
서울 강남구 2024년 1월 아파트 매매 실거래가 조회해줘
```
```
마포구 2024년 6월 전월세 실거래 목록 보여줘
```
```
래미안 원베일리 단지 상세정보 알려줘
```
```
한국부동산원 서울 아파트 매매가격지수 2023~2024년 추이
```
```
KB부동산 PIR 최근 5년 추이 알려줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```

Claude Code 재시작 후 적용됩니다.
