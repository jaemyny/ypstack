# ypstack MCP 설치 프롬프트 — Claude Code (Windows · macOS 공통)

> ## 사용 방법 (⚠️ 반드시 Claude **Code** 에서 실행)
>
> 이 설치는 **Claude Code** 에서만 동작합니다. OS에 맞게 시작하세요:
>
> **macOS**
> 1. 저장소 받기: 터미널에서 `git clone https://github.com/jaemyny/ypstack.git ~/ypstack`
>    (이미 있으면 `git -C ~/ypstack pull`)
> 2. `cd ~/ypstack && claude` (또는 데스크톱 앱 `Code` 탭에서 이 폴더 열기)
> 3. 아래 구분선 **이하 프롬프트 전체**를 복사해 붙여넣고 엔터.
>
> **Windows**
> 1. ZIP 다운로드 → `C:\Users\<사용자명>\ypstack\` 에 풀기
>    (`...\ypstack\stats-realty-mcp\server.py` 가 보이면 정상)
> 2. 데스크톱 앱 `Code` 탭 → 새 채팅 → 📎 로 폴더/ZIP 첨부
>    (또는 PowerShell 에서 `cd "$env:USERPROFILE\ypstack"; claude`)
> 3. 아래 구분선 **이하 프롬프트 전체**를 복사해 붙여넣고 엔터.
>
> ❌ **데스크톱 앱의 `Chat` 탭(또는 Chat 창)에서는 안 됩니다** — 그 Claude는 인터넷 너머
> 격리된 리눅스 샌드박스에서 돌기 때문에 여러분 PC에 파일을 쓰거나 명령을 실행할 수 없습니다.
> 설치 안내만 출력될 뿐 실제 설치가 진행되지 않습니다.
>
> ※ 설치 중 명령 실행 허용을 물으면 승인해 주세요. 완료까지 약 5~10분.

---

이 PC에 있는 ypstack 저장소(macOS: `~/ypstack`, Windows: `C:\Users\<사용자명>\ypstack`)의
MCP 서버들을 이 PC의 **Claude Code** 에서 쓸 수 있도록 설치·설정해 줘. 너는 지금 내 PC에서
실행 중인 Claude Code(Code 탭 또는 CLI)이므로 실제 파일·명령 접근이 가능하다.
저장소가 위 경로에 없으면 먼저 `git clone https://github.com/jaemyny/ypstack.git` 으로 받은 뒤,
아래 단계를 순서대로 엄격히 따라라.

**1. 환경 점검 및 런타임 설치**
- `python3 --version`(또는 `python --version`), `node --version` 으로 설치 여부 확인.
- Python 이 없으면 설치를 진행하지 말고 아래만 출력하고 중단:
  - macOS: `brew install python` (Homebrew 없으면 https://brew.sh 안내)
  - Windows: https://www.python.org/downloads/ 에서 다운로드, 첫 화면 **"Add Python to PATH"** 체크
  - 설치 후 Claude Code 를 새로 시작해 다시 이 프롬프트 실행
- Node.js 가 없으면 설치 시도 — macOS: `brew install node`, Windows: `winget install OpenJS.NodeJS.LTS`.
  실패하면 보고만 하고 stats-pubprice 서버는 건너뛰고 나머지는 계속 진행.
- Python 3.14 이면 `stats-realty-mcp` 의 `PublicDataReader` 호환 문제가 있을 수 있으니
  설치 오류 시 3.12/3.13 사용을 권고하라.

**2. 의존성 설치**
- Python 9개 — 각 폴더에서 `pip install -r requirements.txt` (없으면 `python3 -m pip install ...`):
  stats-realty-mcp, stats-mcp, stats-finance-mcp, stats-job-mcp, stats-biz-mcp,
  stats-transit-mcp, stats-edu-mcp, stats-env-mcp, kb-price-mcp
- Node 1개 — `stats-pubprice-mcp` 폴더에서 `npm install`

**3. 설정 파일에 병합할 서버 목록 (템플릿 — 두 플레이스홀더를 이 PC 값으로 치환)**

아래 JSON 의 `mcpServers` 를 등록 대상으로 삼아라. 치환 규칙:
- `PYBIN` → 이 PC에서 동작하는 파이썬 실행기 (macOS: `python3`, Windows: `python`)
- `<YPSTACK>` → 이 PC의 ypstack 절대경로, forward slash(`/`) 사용
  (macOS: `/Users/<사용자명>/ypstack`, Windows: `C:/Users/<사용자명>/ypstack`)
- `node` 는 그대로 둔다.

```json
{
  "mcpServers": {
    "stats-realty": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-realty-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
        "REB_API_KEY": "a32cd4fb1ae6467a8870277d0a9d6386",
        "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q="
      }
    },
    "kb-price": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/kb-price-mcp/server.py"]
    },
    "stats": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-mcp/server.py"],
      "env": {
        "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
        "SGIS_CONSUMER_KEY": "f18615e1d50242f1a3df",
        "SGIS_CONSUMER_SECRET": "f4bef8ce9c30440ca904",
        "SEOUL_API_KEY": "67676975446a6165313032546e4a466e",
        "GG_API_KEY": "b4c53be41a034da98e8093f138a700d8"
      }
    },
    "stats-finance": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-finance-mcp/server.py"],
      "env": {
        "ECOS_API_KEY": "WN3E49K1TCIX2YIIVBW4",
        "DART_API_KEY": "660ed63c5aecc383b9e03168595fd8bcbca3858f"
      }
    },
    "stats-job": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-job-mcp/server.py"],
      "env": {
        "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
        "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830"
      }
    },
    "stats-biz": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-biz-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
        "SEOUL_API_KEY": "67676975446a6165313032546e4a466e",
        "REB_API_KEY": "a32cd4fb1ae6467a8870277d0a9d6386"
      }
    },
    "stats-transit": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-transit-mcp/server.py"],
      "env": {
        "SEOUL_API_KEY": "67676975446a6165313032546e4a466e",
        "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q="
      }
    },
    "stats-edu": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-edu-mcp/server.py"],
      "env": {
        "NEIS_API_KEY": "3f9764de834045c7afb05a92acb90b18"
      }
    },
    "stats-env": {
      "command": "PYBIN",
      "args": ["<YPSTACK>/stats-env-mcp/server.py"],
      "env": {
        "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
        "SEOUL_API_KEY": "67676975446a6165313032546e4a466e",
        "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q="
      }
    },
    "stats-pubprice": {
      "command": "node",
      "args": ["<YPSTACK>/stats-pubprice-mcp/src/index.js"],
      "env": {
        "VWORLD_API_KEY": "ED4B0E1F-6D78-3D81-9301-8471900DD71F",
        "VWORLD_DOMAIN": "localhost"
      }
    }
  }
}
```

**4. 설정 파일에 병합 (기존 항목 보존, 위 서버만 추가/갱신)**

- **Claude Code (필수):** 홈 디렉터리의 **`.claude.json` 파일** 의 **최상위 `mcpServers` 키**에 병합하라.
  (macOS: `~/.claude.json`, Windows: `%USERPROFILE%\.claude.json`)
  - ⚠️ `~/.claude/mcp.json` 이 아니다 — Claude Code 는 그 파일을 읽지 않는다. 반드시 `~/.claude.json` 이다.
  - 파일이 없으면 새로 만들고, 있으면 JSON 을 읽어 기존 내용 보존 후 `mcpServers` 만 병합하라.
- **Claude Desktop Chat (선택, 별도 Chat 앱에서도 쓸 때만):** 같은 `mcpServers` 를 아래에 병합하라.
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
    (`%APPDATA%\Claude\` 가 없고 `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\` 가
    있으면 = MS Store 설치판, 그쪽에 써라.)

**5. 검증 및 완료 보고**
- 어느 파일에 어떤 서버를 넣었는지 이름 목록을 출력하라.
- Claude Code 는 재시작이 필요하다: 현재 세션/창을 종료하고 다시 시작한 뒤
  `/mcp` 를 입력해 `connected` 표시를 확인하라고 안내하라.
- Claude Desktop Chat 도 설정했다면 앱을 완전히 종료 후 재실행하라고 안내하라.

---

> ## 업데이트 방법 (나중에 새 버전이 나오면)
>
> 서버가 "업데이트 있음" 을 알리면:
> 1. `git -C ~/ypstack pull` (Windows: `git -C "$env:USERPROFILE\ypstack" pull`)
> 2. Claude Code 에서 위 설치 프롬프트를 **다시 한 번** 실행 (의존성·설정 재반영)
