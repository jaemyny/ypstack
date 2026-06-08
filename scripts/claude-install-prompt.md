# ypstack MCP 설치 프롬프트 — Windows · Claude Desktop / Claude Code

> ## 사용 방법
>
> 1. 이 ZIP 파일(또는 폴더)을 Claude 채팅창 하단의 📎 클립 아이콘으로 첨부하세요.
> 2. 아래 구분선 이하의 프롬프트 전체를 복사해서 채팅창에 붙여넣으세요.
> 3. 엔터를 누르면 Claude가 자동으로 설치를 진행합니다.
>
> ※ 완료까지 약 5~10분 소요 | Python이나 Node.js가 없으면 설치 방법을 안내해 드립니다.

---

현재 첨부된 파일(ypstack 저장소)에 포함된 MCP 서버들을 이 Windows 환경의 Claude Desktop 및 Claude Code에서 사용할 수 있도록 설치하고 설정해 줘. 아래 단계별 지침을 순서대로 엄격하게 따라 진행해 줘.

**1. 환경 점검 및 런타임 설치**
- Python과 Node.js가 설치되어 있는지 확인해.
- Python이 없으면 설치 안내를 먼저 출력하고 중단해 줘:
  - https://www.python.org/downloads/ 에서 다운로드
  - 설치 첫 화면에서 반드시 "Add Python to PATH" 체크
  - 설치 완료 후 이 프롬프트 다시 실행
- Node.js가 없으면 PowerShell에서 `winget install OpenJS.NodeJS.LTS` 로 자동 설치해.
- Python 버전 확인: `stats-realty-mcp`의 `PublicDataReader` 패키지가 Python 3.14에서 호환 문제가 있을 수 있으니 확인하고 문제 시 보고해 줘.

**2. MCP 소스 배치 및 의존성 설치**
- 첨부된 ypstack 소스를 `C:\Users\<현재사용자명>\ypstack\` 경로에 복사/배치해.
  (이미 해당 경로에 있으면 그대로 사용해도 됨)
- **Python 기반 MCP 9개** — 각 폴더에서 `pip install -r requirements.txt` 실행:
  stats-realty-mcp, stats-mcp, stats-finance-mcp, stats-job-mcp, stats-biz-mcp,
  stats-transit-mcp, stats-edu-mcp, stats-env-mcp, kb-price-mcp
- **Node.js 기반 MCP** — stats-pubprice-mcp 폴더에서 `npm install` 실행

**3. API 키 (별도 발급 불필요 — 아래 값 그대로 사용)**

| 키 이름 | 값 |
|---|---|
| DATA_GO_KR_KEY | 5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830 |
| REB_API_KEY | a32cd4fb1ae6467a8870277d0a9d6386 |
| KOSIS_API_KEY | Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q= |
| SGIS_CONSUMER_KEY | f18615e1d50242f1a3df |
| SGIS_CONSUMER_SECRET | f4bef8ce9c30440ca904 |
| SEOUL_API_KEY | 67676975446a6165313032546e4a466e |
| GG_API_KEY | b4c53be41a034da98e8093f138a700d8 |
| ECOS_API_KEY | WN3E49K1TCIX2YIIVBW4 |
| DART_API_KEY | 660ed63c5aecc383b9e03168595fd8bcbca3858f |
| NEIS_API_KEY | 3f9764de834045c7afb05a92acb90b18 |
| VWORLD_API_KEY | ED4B0E1F-6D78-3D81-9301-8471900DD71F |
| VWORLD_DOMAIN | localhost |

**4. 설정 파일 업데이트 (두 경로 모두)**
아래 두 파일에 `mcpServers` 항목을 생성하거나 업데이트해 줘. 기존 항목은 유지하고 ypstack 서버 10개만 추가/업데이트해:
- Claude Desktop: `%APPDATA%\Roaming\Claude\claude_desktop_config.json`
- Claude Code: `%USERPROFILE%\.claude\mcp.json`

등록할 서버 목록:
- Python 기반 (command: "python"): stats-realty, kb-price, stats, stats-finance, stats-job, stats-biz, stats-transit, stats-edu, stats-env
- Node.js 기반 (command: "node"): stats-pubprice

각 서버 args에는 `C:\Users\<현재사용자명>\ypstack\<서버폴더명>\server.py(또는 server.js)` 절대 경로 사용.
해당하는 API 키를 env 항목에 정확히 주입해.

**5. 검증 및 완료 보고**
설정 완료 후:
- 저장된 두 config 파일의 mcpServers 항목(서버 이름 목록)을 간략히 출력
- Claude Desktop 재시작 방법 안내
- 채팅창에 `/mcp` 입력 시 connected로 표시되면 완료임을 안내
