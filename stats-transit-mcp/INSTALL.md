# stats-transit-mcp 설치 가이드

Claude Code에서 자연어로 지하철 승하차·실시간 도착·버스노선·교통통계를 조회하는 MCP 서버입니다.

---

## 제공 도구 (5개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `seoul_get_subway_ridership` | 지하철역별 승하차 통계 (월별) | SEOUL |
| `seoul_get_subway_realtime` | 지하철 실시간 도착 정보 | SEOUL |
| `seoul_get_bus_route_info` | 버스 노선 정보 조회 | SEOUL |
| `kosis_get_transit_stats` | KOSIS 교통·이동 통계 | KOSIS |
| `seoul_get_station_info` | 지하철역 기본 정보 조회 | SEOUL |

---

## 필요 API 키

### 서울 열린데이터광장
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
bash ~/ypstack/stats-transit-mcp/setup.sh
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
    "stats-transit": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-transit-mcp/server.py"],
      "env": {
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
강남역 2024년 3월 지하철 승하차 인원 알려줘
```
```
2호선 홍대입구역 실시간 열차 도착 정보
```
```
서울 370번 버스 노선 정보 조회해줘
```
```
서울시 지하철 이용객 수 연도별 추이 보여줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
