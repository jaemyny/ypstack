# stats-finance-mcp 설치 가이드

Claude Code에서 자연어로 금리·경제지표·주택담보대출금리·기업공시·재무제표를 조회하는 MCP 서버입니다.

---

## 제공 도구 (7개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `ecos_search_stats` | 한국은행 경제통계 항목 검색 | ECOS |
| `ecos_get_interest_rate` | 기준금리·CD·COFIX 금리 조회 | ECOS |
| `ecos_get_economic_indicator` | GDP·CPI·환율·실업률·통화량 | ECOS |
| `ecos_get_housing_loan_rate` | 주택담보대출 금리 추이 | ECOS |
| `dart_search_company` | OpenDART 기업 검색 | DART |
| `dart_get_disclosure_list` | 기업 공시 목록 조회 | DART |
| `dart_get_financial_statement` | 기업 재무제표 조회 | DART |

---

## 필요 API 키

### ECOS (한국은행 경제통계시스템)
1. [https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary](https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary) 접속
2. 회원가입 후 **인증키 신청** 메뉴에서 발급 (무료)

### OpenDART (금융감독원 전자공시)
1. [https://opendart.fss.or.kr](https://opendart.fss.or.kr) 접속
2. 회원가입 후 **API 신청** → 인증키 발급 (무료)

---

## 설치 방법 (자동)

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/stats-finance-mcp/setup.sh
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
    "stats-finance": {
      "command": "python3",
      "args": ["/Users/사용자명/ypstack/stats-finance-mcp/server.py"],
      "env": {
        "ECOS_API_KEY": "여기에_한국은행_ECOS_키",
        "DART_API_KEY": "여기에_OpenDART_키"
      }
    }
  }
}
```

### 3. Claude Code 재시작

---

## 사용 예시

```
한국은행 기준금리 2022년부터 2024년까지 추이 보여줘
```
```
소비자물가지수 최근 3년 추이 조회해줘
```
```
주택담보대출 금리 2023~2024년 월별 추이 알려줘
```
```
삼성전자 2023년 사업보고서 공시 목록 보여줘
```
```
카카오 2023년 연간 재무제표 조회해줘
```

---

## 업데이트

```bash
cd ~/ypstack && git pull
```
