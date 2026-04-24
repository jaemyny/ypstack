# ypstack

유진아빠의 커스텀 Claude Code 슬래시 커맨드 모음.
[gstack](https://github.com/garrytan/gstack)(Garry Tan)에서 영감을 받아 만든 개인 스킬셋.

모든 스킬은 `/yp-` 접두사로 시작합니다.

## 스킬 목록

| 스킬 | 설명 |
|------|------|
| [`/yp-dev-log`](./yp-dev-log) | Phase 완료 시 Confluence용 Dev Log 자동 생성 + 자동 게시 |

## 설치 방법

### 전체 ypstack 설치

```bash
git clone https://github.com/jaemyny/ypstack.git ~/.claude/skills/ypstack
```

### `yp-dev-log`만 설치

```bash
git clone https://github.com/jaemyny/ypstack.git /tmp/ypstack
mkdir -p ~/.claude/skills/ypstack
cp -r /tmp/ypstack/yp-dev-log ~/.claude/skills/ypstack/yp-dev-log
rm -rf /tmp/ypstack
```

### 업데이트

```bash
cd ~/.claude/skills/ypstack && git pull
```

설치 후 Claude Code를 재시작해야 스킬이 인식됩니다.

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
