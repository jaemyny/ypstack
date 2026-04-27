# confluence-label-mcp 설치 가이드

Confluence 페이지에 레이블(태그)을 추가·조회·삭제하는 Claude Code 확장 기능입니다.
한 번 설치하면 Claude Code 어디서나 "이 페이지에 status-verified 레이블 달아줘" 같은 자연어 명령으로 사용할 수 있습니다.

---

## 준비물

- macOS 컴퓨터 (Windows는 하단 참고)
- [Claude Code](https://claude.ai/code) 설치된 상태
- Atlassian(Confluence) 계정

---

## 설치 방법 (자동 — 권장)

터미널(Terminal 앱)을 열고 아래 명령어를 **순서대로** 복사·붙여넣기 합니다.

### 1단계 — 파일 내려받기

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
```

> `~/ypstack` 폴더에 설치됩니다. 다른 위치를 원하면 경로를 바꾸세요.

### 2단계 — 자동 설치 실행

```bash
bash ~/ypstack/confluence-label-mcp/setup.sh
```

스크립트가 안내에 따라 아래 정보를 입력하도록 요청합니다:

| 입력 항목 | 예시 |
|---|---|
| Confluence URL | `https://회사명.atlassian.net/wiki` |
| 이메일 | `yourname@company.com` |
| API 토큰 | (아래 참고) |

### API 토큰 발급 방법

1. 브라우저에서 https://id.atlassian.com/manage-profile/security/api-tokens 접속
2. **Create API token** 버튼 클릭
3. 이름 입력 (예: `claude-code`) → **Create** 클릭
4. 화면에 표시된 토큰 값을 복사해서 스크립트에 붙여넣기

> ⚠️ 토큰은 발급 시 한 번만 보입니다. 반드시 바로 복사하세요.

### 3단계 — Claude Code 재시작

Claude Code를 완전히 종료했다가 다시 실행합니다.

---

## 설치 확인

Claude Code를 열고 아무 대화창에나 다음과 같이 입력해 보세요:

```
Confluence 페이지 2149286590의 레이블을 조회해줘
```

레이블 목록이 응답으로 오면 설치 성공입니다.

---

## 사용 예시

Claude Code에서 자연어로 요청하면 됩니다:

```
페이지 2149286590에 status-verified, lvl3-expert 레이블을 추가해줘
```

```
페이지 2149286590에서 status-draft 레이블을 삭제해줘
```

```
페이지 2149286590의 현재 레이블을 보여줘
```

> 페이지 ID는 Confluence 페이지 URL에서 확인할 수 있습니다.
> 예: `...atlassian.net/wiki/spaces/SPACE/pages/`**`2149286590`**`/페이지제목`

---

## 수동 설치 (자동 스크립트가 안 될 때)

### 1. Python 패키지 설치

```bash
python3 -m pip install mcp[cli] httpx
```

### 2. 설정 파일 만들기

`~/.claude/mcp.json` 파일을 텍스트 편집기로 열고 (없으면 새로 만들기):

```json
{
  "mcpServers": {
    "confluence-label": {
      "command": "python3",
      "args": ["/Users/여기에_사용자명/ypstack/confluence-label-mcp/server.py"],
      "env": {
        "CONFLUENCE_URL": "https://회사명.atlassian.net/wiki",
        "CONFLUENCE_EMAIL": "your@email.com",
        "CONFLUENCE_TOKEN": "여기에_API_토큰"
      }
    }
  }
}
```

> `args` 의 경로는 실제 파일 위치로 바꿔야 합니다.
> 터미널에서 `echo ~/ypstack/confluence-label-mcp/server.py` 를 실행하면 정확한 경로를 확인할 수 있습니다.

### 3. Claude Code 재시작

---

## 업데이트

새 버전이 나왔을 때는 터미널에서:

```bash
cd ~/ypstack && git pull
```

이후 Claude Code를 재시작하면 최신 버전이 적용됩니다.

---

## 보안 주의사항

- `~/.claude/mcp.json` 파일에는 API 토큰이 들어있습니다. 이 파일을 다른 사람과 공유하거나 GitHub에 올리지 마세요.
- API 토큰이 노출됐다면 https://id.atlassian.com/manage-profile/security/api-tokens 에서 즉시 폐기하세요.
- 이 레포의 `.mcp.json.example` 파일은 토큰이 비어 있는 예시 파일로, 공유해도 안전합니다.

---

## 문제 해결

**`python3: command not found` 오류**
→ Python이 설치되어 있지 않습니다. https://www.python.org/downloads/ 에서 설치 후 재시도.

**`No module named 'mcp'` 오류**
→ `python3 -m pip install mcp[cli] httpx` 를 실행한 뒤 Claude Code 재시작.

**응답이 없거나 "MCP 서버 연결 실패"**
→ `~/.claude/mcp.json` 의 경로와 토큰을 다시 확인하세요.

**그 외 문제**
→ [이슈 등록](https://github.com/jaemyny/ypstack/issues)하거나 유진아빠에게 문의.

---

## Windows 사용자

Windows에서 Claude Code 사용 시 WSL(Windows Subsystem for Linux) 환경을 추천합니다.
WSL 터미널에서 위 macOS 가이드와 동일하게 진행하세요.
