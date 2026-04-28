# realty-data-mcp 설치 가이드

Claude Code에서 자연어로 한국 부동산·경제 데이터를 조회하는 MCP 서버입니다.  
한 번 설치하면 **"서울 강남구 2024년 1월 매매 실거래가 알려줘"** 같은 질문에 실시간 데이터로 바로 답해줍니다.

---

## 제공 도구 (9개)

| 도구 | 설명 | 필요 API 키 |
|------|------|-------------|
| `kosis_search_stats` | 통계청 통계표 키워드 검색 | KOSIS |
| `kosis_get_data` | KOSIS 통계표 데이터 직접 조회 | KOSIS |
| `kosis_get_population` | 지역별 인구 통계 | KOSIS |
| `kosis_get_household` | 지역별 세대(가구) 통계 | KOSIS |
| `ecos_search_stats` | 한국은행 경제통계 항목 검색 | ECOS |
| `ecos_get_interest_rate` | 기준금리·CD금리·COFIX 등 조회 | ECOS |
| `rtms_get_lawd_codes` | 지역 법정동코드 조회 | 불필요 |
| `rtms_get_apt_trade` | 아파트 매매 실거래가 조회 | RTMS |
| `rtms_get_apt_rent` | 아파트 전월세 실거래 조회 | RTMS |

---

## 준비물

- macOS 컴퓨터 (Windows는 하단 참고)
- [Claude Code](https://claude.ai/code) 설치된 상태
- API 키 (사용할 서비스만 발급)

---

## API 키 발급 방법

### KOSIS (통계청) — 인구·가구 통계

1. [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp) 접속
2. 회원가입(무료) 후 로그인
3. **OPEN API 활용신청** → 서비스 선택 → 신청 완료
4. **마이페이지 → OPEN API → API 키 확인**에서 키 복사

> ⚠️ KOSIS 키는 Base64 형식입니다. 발급받은 키를 그대로 사용하세요 (디코딩 X).

### ECOS (한국은행) — 금리·경제지표

1. [https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary](https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary) 접속
2. 회원가입(무료) 후 로그인
3. **인증키 신청** 메뉴에서 발급

### RTMS (국토부) — 아파트 실거래가

1. [https://www.data.go.kr](https://www.data.go.kr) 접속
2. "아파트매매실거래자료" 검색 → **국토교통부_아파트매매실거래자료** 선택
3. **활용신청** (일반 인증키, 무료)
4. 마이페이지 → 활용신청 내역 → 일반 인증키 복사

---

## 설치 방법 (자동 — 권장)

터미널(Terminal 앱)을 열고 아래 명령어를 **순서대로** 실행합니다.

### 1단계 — 파일 내려받기

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
```

### 2단계 — 자동 설치 실행

```bash
bash ~/ypstack/realty-data-mcp/setup.sh
```

스크립트가 Python 확인 → 패키지 설치 → API 키 입력 → 설정 파일 등록을 자동으로 처리합니다.

### 3단계 — Claude Code 재시작

Claude Code를 완전히 종료했다가 다시 실행합니다.

---

## 설치 확인

Claude Code를 열고 다음과 같이 입력해 보세요.

```
서울 강남구 2024년 1월 아파트 매매 실거래가를 조회해줘
```

실거래 데이터가 표시되면 설치 성공입니다.

---

## 사용 예시

```
서울 마포구 2024년 3월 아파트 전월세 실거래가 알려줘
```

```
한국은행 기준금리 2022년부터 2024년까지 추이 보여줘
```

```
서울시 25개구별 세대수 현황 표로 만들어줘
```

```
경기도 분당구 59㎡~85㎡ 아파트 2024년 12월 매매가 알려줘
```

```
소비자물가지수 최근 3년 추이 조회해줘
```

---

## 수동 설치 (자동 스크립트가 안 될 때)

### 1. Python 패키지 설치

```bash
python3 -m pip install "mcp[cli]" httpx pydantic
```

### 2. 설정 파일 만들기

`~/.claude/mcp.json` 파일을 텍스트 편집기로 열고 (없으면 새로 만들기):

```json
{
  "mcpServers": {
    "realty-data": {
      "command": "python3",
      "args": ["/Users/여기에_사용자명/ypstack/realty-data-mcp/server.py"],
      "env": {
        "KOSIS_API_KEY": "여기에_KOSIS_키",
        "ECOS_API_KEY":  "여기에_ECOS_키",
        "RTMS_API_KEY":  "여기에_RTMS_키"
      }
    }
  }
}
```

> 경로 확인: 터미널에서 `echo ~/ypstack/realty-data-mcp/server.py` 실행

### 3. Claude Code 재시작

---

## 업데이트

```bash
cd ~/ypstack && git pull
```

이후 Claude Code를 재시작하면 최신 버전이 적용됩니다.

---

## 보안 주의사항

- `~/.claude/mcp.json` 에는 API 키가 포함됩니다. **절대 GitHub에 올리지 마세요.**
- API 키가 노출됐다면 각 발급처에서 즉시 재발급하세요.
- 이 레포의 `.mcp.json.example` 은 키가 비어있는 예시 파일이므로 공유해도 안전합니다.

---

## 문제 해결

**`python3: command not found`**  
→ Python 3.11 이상 설치 필요: https://www.python.org/downloads/

**`No module named 'mcp'`**  
→ `python3 -m pip install "mcp[cli]" httpx pydantic` 후 Claude Code 재시작

**"KOSIS_API_KEY 환경변수가 설정되지 않았습니다"**  
→ `~/.claude/mcp.json` 의 `env.KOSIS_API_KEY` 값을 확인하세요.

**"40,000셀 초과" 오류**  
→ `kosis_get_data` 의 `obj_l1`, `obj_l2`, `itm_id` 파라미터로 조회 범위를 좁혀 재요청하세요.

**그 외 문제**  
→ [이슈 등록](https://github.com/jaemyny/ypstack/issues) 또는 유진아빠에게 문의

---

## Windows 사용자

WSL(Windows Subsystem for Linux) 환경에서 위 macOS 가이드와 동일하게 진행하세요.
