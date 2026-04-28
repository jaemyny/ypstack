# stats-edu-mcp 설치 가이드

Claude Code에서 자연어로 학교 정보·학원 현황·교육 통계를 조회하는 MCP 서버입니다.

---

## 제공 도구 (5개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `neis_get_school_list` | 지역별 학교 목록 조회 | NEIS |
| `neis_get_school_detail` | 학교 상세정보 (학생수·학급수) | NEIS |
| `neis_get_academy_list` | 지역별 학원 목록 조회 | NEIS |
| `neis_get_academy_stats` | 지역별 학원 통계 | NEIS |
| `schoolzone_lookup` | 어린이보호구역(스쿨존) 위치 안내 | 불필요 |

---

## 필요 API 키

### NEIS (교육부 교육통계서비스)
1. [https://open.neis.go.kr](https://open.neis.go.kr) 접속
2. 회원가입 후 **인증키 발급** (무료)
3. 마이페이지에서 API 키 확인

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-edu-mcp/setup.sh
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
    "stats-edu": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-edu-mcp/server.py"],
      "env": {
        "NEIS_API_KEY":  "여기에_NEIS_키",
        "KOSIS_API_KEY": "여기에_KOSIS_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
서울 강남구 초등학교 목록 알려줘
```
```
대치동 학원 현황 조회해줘
```
```
서울 서초구 중학교 학생 수 통계
```
```
경기도 분당 학원 수 통계 보여줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
