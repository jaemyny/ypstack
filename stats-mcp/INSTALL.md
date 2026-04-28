# stats-mcp 설치 가이드

Claude Code에서 자연어로 인구·가구·지역 통계를 조회하는 MCP 서버입니다.  
통계청 KOSIS, SGIS, 서울시 열린데이터, 경기데이터드림을 통합합니다.

---

## 제공 도구 (8개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `kosis_search_stats` | KOSIS 통계표 키워드 검색 | KOSIS |
| `kosis_get_data` | KOSIS 통계표 직접 조회 | KOSIS |
| `kosis_get_population` | 지역별 인구 통계 | KOSIS |
| `kosis_get_household` | 지역별 세대·가구 통계 | KOSIS |
| `kosis_get_household_detail` | 가구주연령×가구원수×시군구 세부 통계 | KOSIS |
| `sgis_get_region_stats` | SGIS 지역 통계 (인구밀도·면적 등) | SGIS |
| `seoul_get_living_population` | 서울시 생활인구 (내국인·외국인) | SEOUL |
| `gg_search_stats` | 경기데이터드림 통계 검색 | GG |

---

## 필요 API 키

### KOSIS (통계청)
1. [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp) 접속
2. 회원가입 후 OPEN API 활용신청
3. 마이페이지 → OPEN API → API 키 확인
> Base64 형식 키를 그대로 사용하세요 (디코딩 X)

### SGIS (통계청 통계지리정보서비스)
1. [https://sgis.kostat.go.kr/view/board/openDataPage](https://sgis.kostat.go.kr/view/board/openDataPage) 접속
2. 회원가입 후 **서비스 키 발급** (consumer_key + consumer_secret 두 값 모두 필요)

### 서울 열린데이터광장
1. [https://data.seoul.go.kr](https://data.seoul.go.kr) 접속
2. 회원가입 → 마이페이지 → **인증키 발급**

### 경기데이터드림 (선택)
1. [https://data.gg.go.kr](https://data.gg.go.kr) 접속
2. 회원가입 후 인증키 발급

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-mcp/setup.sh
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
    "stats": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-mcp/server.py"],
      "env": {
        "KOSIS_API_KEY":        "여기에_KOSIS_키",
        "SGIS_CONSUMER_KEY":    "여기에_SGIS_consumer_key",
        "SGIS_CONSUMER_SECRET": "여기에_SGIS_consumer_secret",
        "SEOUL_API_KEY":        "여기에_서울열린데이터_키",
        "GG_API_KEY":           "여기에_경기데이터드림_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
서울시 25개구별 세대수 현황 표로 만들어줘
```
```
서울 강남구 30대 2인가구 비중 알려줘
```
```
경기도 수원시 인구 통계 최근 5년 추이
```
```
서울 홍대 지역 생활인구 2024년 데이터 조회해줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
