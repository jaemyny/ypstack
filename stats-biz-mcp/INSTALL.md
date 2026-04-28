# stats-biz-mcp 설치 가이드

Claude Code에서 자연어로 상가정보·상권통계·유동인구·상업용 부동산 임대료를 조회하는 MCP 서버입니다.

---

## 제공 도구 (5개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `semas_search_stores_by_district` | 행정구역별 상가업소 목록 조회 | DATA_GO_KR |
| `semas_get_store_stats_by_region` | 지역별 업종·상가 통계 | DATA_GO_KR |
| `semas_search_commercial_area` | 상권 지역 정보 검색 | DATA_GO_KR |
| `seoul_get_floating_population` | 서울시 유동인구 (시간대별) | SEOUL |
| `reb_get_commercial_rent` | 한국부동산원 상업용 부동산 임대료 | REB |

---

## 필요 API 키

### DATA_GO_KR (공공데이터포털) — 소상공인 상가정보
1. [https://www.data.go.kr](https://www.data.go.kr) 접속 후 회원가입
2. "소상공인 상가업소" 검색 → **소상공인시장진흥공단_상가업소 정보** 활용신청
3. 마이페이지 → 일반 인증키(Decoding) 복사

### 서울 열린데이터광장 — 유동인구
1. [https://data.seoul.go.kr](https://data.seoul.go.kr) 접속
2. 회원가입 → 마이페이지 → **인증키 발급**

### REB (한국부동산원 R-ONE) — 상업용 부동산
1. [https://www.reb.or.kr/r-one/main.do](https://www.reb.or.kr/r-one/main.do) 접속
2. 회원가입 후 **OpenAPI 신청** 메뉴에서 발급

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-biz-mcp/setup.sh
```

---

## 수동 설치

### 1. 패키지 설치

```bash
python3 -m pip install "mcp[cli]" httpx pydantic
```

### 2. `~/.claude/mcp.json` 에 추가

```json
{
  "mcpServers": {
    "stats-biz": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-biz-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "여기에_공공데이터포털_키",
        "SEOUL_API_KEY":  "여기에_서울열린데이터_키",
        "REB_API_KEY":    "여기에_한국부동산원_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
서울 마포구 카페 업종 상가 목록 조회해줘
```
```
홍대 상권 주변 상가 통계 알려줘
```
```
서울 강남역 평일 오후 8시 유동인구 데이터
```
```
서울 강남구 오피스 상업용 부동산 임대료 추이
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
