# ypstack

유진아빠의 커스텀 Claude Code 확장 모음.
[gstack](https://github.com/garrytan/gstack)(Garry Tan)에서 영감을 받아 만든 개인 스킬셋.

---

## 포함된 도구

### 슬래시 커맨드 (Slash Commands)

Claude Code에서 `/yp-` 접두사로 호출하는 커맨드입니다.

| 스킬 | 설명 |
|------|------|
| [`/yp-dev-log`](./yp-dev-log) | Phase 완료 시 Confluence용 Dev Log 자동 생성 + 자동 게시 |

### MCP 서버 (MCP Servers)

Claude Code에 연결해 두면 자연어로 외부 서비스를 조작할 수 있는 확장 도구입니다.

| MCP | 설명 | 설치 가이드 |
|-----|------|------------|
| [`confluence-label-mcp`](./confluence-label-mcp/INSTALL.md) | **Confluence 레이블 관리** — Confluence 페이지에 레이블(태그)을 추가·조회·삭제 | [INSTALL.md](./confluence-label-mcp/INSTALL.md) |
| [`realty-data-mcp`](./realty-data-mcp/INSTALL.md) | **한국 부동산·경제 데이터** — 통계청 KOSIS(인구·가구), 한국은행 ECOS(금리), 국토부 RTMS(아파트 실거래가) | [INSTALL.md](./realty-data-mcp/INSTALL.md) |

---

## 슬래시 커맨드 설치 방법

### 전체 ypstack 설치

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
```

### `yp-dev-log`만 설치

```bash
git clone https://github.com/jaemyny/ypstack.git /tmp/ypstack
mkdir -p ~/ypstack
cp -r /tmp/ypstack/yp-dev-log ~/ypstack/yp-dev-log
rm -rf /tmp/ypstack
```

### 업데이트

```bash
cd ~/ypstack && git pull
```

설치 후 Claude Code를 재시작해야 스킬이 인식됩니다.

---

## MCP 서버 설치 방법

각 MCP 서버는 별도 설치 과정이 필요합니다. 각 폴더의 `INSTALL.md`를 참고하세요.

### Confluence 레이블 관리 MCP (`confluence-label-mcp`) 빠른 시작

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/confluence-label-mcp/setup.sh
```

→ 자세한 내용: [confluence-label-mcp/INSTALL.md](./confluence-label-mcp/INSTALL.md)

### 한국 부동산·경제 데이터 MCP (`realty-data-mcp`) 빠른 시작

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/realty-data-mcp/setup.sh
```

→ 자세한 내용: [realty-data-mcp/INSTALL.md](./realty-data-mcp/INSTALL.md)

## 환경 변수 (전역)

각 스킬이 외부 API를 호출할 때 사용하는 토큰/시크릿은 전역 위치에 둡니다:

```bash
mkdir -p ~/.config/ypstack && chmod 700 ~/.config/ypstack
# ~/.config/ypstack/.env 에 필요한 환경 변수 기록
chmod 600 ~/.config/ypstack/.env
```

구체적인 필요 환경 변수는 각 스킬의 `SKILL.md` 참조.

## 스킬셋 관리

- **gstack**: `~/.claude/skills/gstack/` (Garry Tan, `gstack-upgrade`로 업데이트)
- **ypstack**: `~/.claude/skills/ypstack/` (유진아빠 자체 관리, `git pull`로 업데이트)

두 스킬셋은 독립적이며 충돌하지 않습니다.

## 라이선스

MIT
