# stats-env-mcp 설치 가이드

Claude Code에서 자연어로 대기질·공원·환경 통계를 조회하는 MCP 서버입니다.

---

## 제공 도구 (5개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `airkorea_get_realtime_air` | 실시간 대기오염 정보 (측정소별) | DATA_GO_KR |
| `airkorea_get_station_list` | 대기질 측정소 목록 조회 | DATA_GO_KR |
| `airkorea_get_region_avg` | 시도별 대기질 평균 | DATA_GO_KR |
| `seoul_get_park_list` | 서울시 공원 목록 및 정보 | SEOUL |
| `kosis_get_env_stats` | KOSIS 환경 통계 (폐기물·상하수도 등) | KOSIS |

---

## 필요 API 키

### DATA_GO_KR (공공데이터포털) — 에어코리아 대기정보
1. [https://www.data.go.kr](https://www.data.go.kr) 접속 후 회원가입
2. "에어코리아 대기오염정보" 검색 → **한국환경공단_에어코리아_대기오염정보** 활용신청
3. 마이페이지 → 일반 인증키(Decoding) 복사

### 서울 열린데이터광장 — 공원 정보
1. [https://data.seoul.go.kr](https://data.seoul.go.kr) 접속
2. 회원가입 → 마이페이지 → **인증키 발급**

### KOSIS (통계청)
1. [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp) 접속
2. 회원가입 후 OPEN API 활용신청
3. 마이페이지 → OPEN API → API 키 확인
> Base64 형식 키를 그대로 사용하세요 (디코딩 X)

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-env-mcp/setup.sh
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
    "stats-env": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-env-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "여기에_공공데이터포털_키",
        "SEOUL_API_KEY":  "여기에_서울열린데이터_키",
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
서울 종로구 현재 대기질 알려줘
```
```
서울시 PM2.5 대기오염 측정소 목록 보여줘
```
```
서울 강남구 공원 목록 조회해줘
```
```
전국 폐기물 발생량 통계 최근 5년 추이
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
