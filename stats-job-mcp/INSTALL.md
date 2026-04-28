# stats-job-mcp 설치 가이드

Claude Code에서 자연어로 고용·임금·사업체·국민연금 통계를 조회하는 MCP 서버입니다.

---

## 제공 도구 (5개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `kosis_get_employment_stats` | 지역별·산업별 고용 통계 | KOSIS |
| `kosis_get_wage_stats` | 지역별·업종별 임금 통계 | KOSIS |
| `kosis_get_business_count` | 지역별 사업체 수 통계 | KOSIS |
| `kosis_search_job_stats` | 고용·임금 관련 통계표 검색 | KOSIS |
| `nps_get_subscriber_stats` | 국민연금 지역별 가입자 통계 | DATA_GO_KR |

---

## 필요 API 키

### KOSIS (통계청)
1. [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp) 접속
2. 회원가입 후 OPEN API 활용신청
3. 마이페이지 → OPEN API → API 키 확인
> Base64 형식 키를 그대로 사용하세요 (디코딩 X)

### DATA_GO_KR (공공데이터포털) — 국민연금 가입자
1. [https://www.data.go.kr](https://www.data.go.kr) 접속 후 회원가입
2. "국민연금 가입자" 검색 → 활용신청
3. 마이페이지 → 일반 인증키(Decoding) 복사

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-job-mcp/setup.sh
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
    "stats-job": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-job-mcp/server.py"],
      "env": {
        "KOSIS_API_KEY":   "여기에_KOSIS_키",
        "DATA_GO_KR_KEY":  "여기에_공공데이터포털_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
서울시 구별 취업자 수 현황 알려줘
```
```
제조업 평균 임금 최근 3년 추이 보여줘
```
```
경기도 수원시 사업체 수 통계 조회해줘
```
```
국민연금 가입자 수 서울 강남구 기준 알려줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
