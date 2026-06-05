#!/usr/bin/env bash
# update-stats-pack.sh — ypstack 부동산 통계 MCP 업데이트 스크립트
#
# 사용법: bash ~/ypstack/scripts/update-stats-pack.sh
#
# 수행 내용:
#   1. git pull (코드 + 팀 키 + VERSION 최신화)
#   2. Python 패키지 재설치 (신규 의존성 반영)
#   3. ~/.claude/mcp.json 재생성 (새 경로·키 반영)
#   4. 설치 버전 기록 갱신

set -euo pipefail

YPSTACK="${HOME}/ypstack"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}✔${NC}  $*"; }
info() { echo -e "${BLUE}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*" >&2; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   ypstack 부동산 통계 MCP 업데이트"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

[[ -d "${YPSTACK}/.git" ]] || { err "저장소를 찾을 수 없습니다: ${YPSTACK}"; exit 1; }

# 1. git pull
info "저장소 최신화..."
OLD_VER=$(head -1 "${YPSTACK}/scripts/VERSION" 2>/dev/null || echo "?")
git -C "${YPSTACK}" pull --quiet
NEW_VER=$(head -1 "${YPSTACK}/scripts/VERSION" 2>/dev/null || echo "?")

if [[ "${OLD_VER}" == "${NEW_VER}" ]]; then
  log "이미 최신 버전입니다 (${NEW_VER})"
else
  log "버전 업데이트: ${OLD_VER} → ${NEW_VER}"
fi

# 2. 재설치 (install-stats-pack.sh 호출)
echo ""
bash "${YPSTACK}/scripts/install-stats-pack.sh"

# 3. 업데이트 체크 마커 초기화 (다음 MCP 시작 시 재확인)
rm -f "${HOME}/.config/ypstack/.last_check"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "업데이트 완료! Claude Code를 재시작하세요."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
