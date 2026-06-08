#!/usr/bin/env bash
# install-stats-pack.sh — ypstack 부동산 통계 MCP 통합 설치 스크립트
#
# 사용법:
#   bash ~/ypstack/scripts/install-stats-pack.sh
#   bash ~/ypstack/scripts/install-stats-pack.sh --env-file ~/team-keys.env
#
# team-keys.env 형식은 scripts/team-keys.env.template 참조

set -euo pipefail

YPSTACK_DIR="${HOME}/ypstack"
MCP_JSON="${HOME}/.claude/mcp.json"
ENV_FILE=""
PYTHON="$(command -v python3.11 2>/dev/null || command -v python3 2>/dev/null || echo "python3")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}✔${NC}  $*"; }
info() { echo -e "${BLUE}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*" >&2; }

while [[ $# -gt 0 ]]; do
  case $1 in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--env-file /path/to/team-keys.env]"
      echo ""
      echo "  --env-file  팀 공유 API 키 파일 경로 (team-keys.env)"
      echo "              파일 형식: scripts/team-keys.env.template 참조"
      exit 0 ;;
    *) err "알 수 없는 옵션: $1"; exit 1 ;;
  esac
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   ypstack 부동산 통계 MCP 10종 통합 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. 사전 요구사항 ──────────────────────────────────────────
info "사전 요구사항 확인..."
if ! command -v python3 &>/dev/null; then
  err "Python 3이 필요합니다. 설치: brew install python@3.11"
  exit 1
fi
if ! command -v git &>/dev/null; then
  err "git이 필요합니다. 설치: xcode-select --install"
  exit 1
fi
log "Python: $($PYTHON --version 2>&1)"
log "git: $(git --version)"

# ── 2. 저장소 클론 / 업데이트 ────────────────────────────────
echo ""
info "저장소 준비: ${YPSTACK_DIR}"
if [[ -d "${YPSTACK_DIR}/.git" ]]; then
  git -C "${YPSTACK_DIR}" pull --quiet --ff-only
  log "저장소 업데이트 완료"
else
  git clone https://github.com/jaemyny/ypstack.git "${YPSTACK_DIR}"
  log "저장소 클론 완료"
fi

# ── 3. Python 패키지 설치 (9개 Python 기반 MCP) ──────────────
echo ""
info "Python 패키지 설치 중 (9개)..."

PYTHON_MCPS=(
  stats-realty-mcp
  stats-mcp
  stats-finance-mcp
  stats-job-mcp
  stats-biz-mcp
  stats-transit-mcp
  stats-edu-mcp
  stats-env-mcp
  kb-price-mcp
)

for mcp in "${PYTHON_MCPS[@]}"; do
  REQ="${YPSTACK_DIR}/${mcp}/requirements.txt"
  if [[ -f "$REQ" ]]; then
    $PYTHON -m pip install -q -r "$REQ"
    log "  ${mcp}"
  else
    warn "  ${mcp}: requirements.txt 없음, 건너뜀"
  fi
done

# ── 4. stats-pubprice-mcp (Node.js 기반) ─────────────────────
echo ""
PUBPRICE_DIR="${YPSTACK_DIR}/stats-pubprice-mcp"
PUBPRICE_INSTALLED=false

if [[ -d "${PUBPRICE_DIR}" ]]; then
  if command -v node &>/dev/null; then
    info "stats-pubprice-mcp (Node.js) 설치 중..."
    (cd "${PUBPRICE_DIR}" && npm install --silent)
    log "  stats-pubprice-mcp"
    PUBPRICE_INSTALLED=true
  else
    warn "Node.js 없음 → stats-pubprice-mcp 건너뜀"
    warn "나중에 설치: brew install node && cd ${PUBPRICE_DIR} && npm install"
  fi
else
  warn "stats-pubprice-mcp 디렉토리 없음 → 건너뜀 (준비 중)"
fi

# ── 5. API 키 로드 ────────────────────────────────────────────
echo ""
# --env-file 미지정 시 저장소의 team-keys.env 자동 사용
if [[ -z "${ENV_FILE}" && -f "${YPSTACK_DIR}/scripts/team-keys.env" ]]; then
  ENV_FILE="${YPSTACK_DIR}/scripts/team-keys.env"
  info "팀 공용 키 자동 사용: ${ENV_FILE}"
fi

if [[ -n "${ENV_FILE}" ]]; then
  [[ -f "${ENV_FILE}" ]] || { err "env 파일을 찾을 수 없습니다: ${ENV_FILE}"; exit 1; }
  info "API 키 로드: ${ENV_FILE}"
  set -o allexport
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +o allexport
  log "API 키 로드 완료"
else
  warn "API 키 미설정 → ~/.claude/mcp.json에 빈 값으로 저장됩니다."
  warn "팀 키 파일 위치: ${YPSTACK_DIR}/scripts/team-keys.env"
fi

# ── 6. ~/.claude/mcp.json 생성 (Python으로 안전하게) ─────────
echo ""
info "~/.claude/mcp.json 생성 중..."
mkdir -p "${HOME}/.claude"

PUBPRICE_FLAG="${PUBPRICE_INSTALLED}" \
$PYTHON - "${YPSTACK_DIR}" << 'PYEOF'
import json, os, sys

ypstack = sys.argv[1]
pubprice_ok = os.environ.get("PUBPRICE_FLAG", "false") == "true"
mcp_path = os.path.expanduser("~/.claude/mcp.json")

def k(name): return os.environ.get(name, "")

new_servers = {
    "stats-realty": {
        "command": "python3",
        "args": [f"{ypstack}/stats-realty-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": k("DATA_GO_KR_KEY"),
            "REB_API_KEY":    k("REB_API_KEY"),
            "KOSIS_API_KEY":  k("KOSIS_API_KEY"),
        },
    },
    "kb-price": {
        "command": "python3",
        "args": [f"{ypstack}/kb-price-mcp/server.py"],
    },
    "stats": {
        "command": "python3",
        "args": [f"{ypstack}/stats-mcp/server.py"],
        "env": {
            "KOSIS_API_KEY":        k("KOSIS_API_KEY"),
            "SGIS_CONSUMER_KEY":    k("SGIS_CONSUMER_KEY"),
            "SGIS_CONSUMER_SECRET": k("SGIS_CONSUMER_SECRET"),
            "SEOUL_API_KEY":        k("SEOUL_API_KEY"),
            "GG_API_KEY":           k("GG_API_KEY"),
        },
    },
    "stats-finance": {
        "command": "python3",
        "args": [f"{ypstack}/stats-finance-mcp/server.py"],
        "env": {
            "ECOS_API_KEY": k("ECOS_API_KEY"),
            "DART_API_KEY": k("DART_API_KEY"),
        },
    },
    "stats-job": {
        "command": "python3",
        "args": [f"{ypstack}/stats-job-mcp/server.py"],
        "env": {
            "KOSIS_API_KEY":  k("KOSIS_API_KEY"),
            "DATA_GO_KR_KEY": k("DATA_GO_KR_KEY"),
        },
    },
    "stats-biz": {
        "command": "python3",
        "args": [f"{ypstack}/stats-biz-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": k("DATA_GO_KR_KEY"),
            "SEOUL_API_KEY":  k("SEOUL_API_KEY"),
            "REB_API_KEY":    k("REB_API_KEY"),
        },
    },
    "stats-transit": {
        "command": "python3",
        "args": [f"{ypstack}/stats-transit-mcp/server.py"],
        "env": {
            "SEOUL_API_KEY": k("SEOUL_API_KEY"),
            "KOSIS_API_KEY": k("KOSIS_API_KEY"),
        },
    },
    "stats-edu": {
        "command": "python3",
        "args": [f"{ypstack}/stats-edu-mcp/server.py"],
        "env": {
            "NEIS_API_KEY": k("NEIS_API_KEY"),
        },
    },
    "stats-env": {
        "command": "python3",
        "args": [f"{ypstack}/stats-env-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": k("DATA_GO_KR_KEY"),
            "SEOUL_API_KEY":  k("SEOUL_API_KEY"),
            "KOSIS_API_KEY":  k("KOSIS_API_KEY"),
        },
    },
}

if pubprice_ok:
    new_servers["stats-pubprice"] = {
        "command": "node",
        "args": [f"{ypstack}/stats-pubprice-mcp/server.js"],
        "env": {
            "VWORLD_API_KEY": k("VWORLD_API_KEY"),
            "VWORLD_DOMAIN":  k("VWORLD_DOMAIN"),
        },
    }

# 기존 mcp.json에 병합 (다른 MCP 설정 유지)
existing = {}
if os.path.exists(mcp_path):
    try:
        with open(mcp_path) as f:
            existing = json.load(f)
    except Exception:
        pass

existing.setdefault("mcpServers", {})
existing["mcpServers"].update(new_servers)

with open(mcp_path, "w") as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"저장: {mcp_path}")
PYEOF

# ── 7. 설치 버전 기록 ─────────────────────────────────────────
VER_FILE="${YPSTACK_DIR}/scripts/VERSION"
if [[ -f "${VER_FILE}" ]]; then
  INSTALLED_VER=$(head -1 "${VER_FILE}")
  mkdir -p "${HOME}/.config/ypstack"
  echo "${INSTALLED_VER}" > "${HOME}/.config/ypstack/installed_version"
  # 업데이트 체크 마커 초기화 (방금 설치했으므로 다음 MCP 시작 때 재확인)
  rm -f "${HOME}/.config/ypstack/.last_check"
  log "버전 기록: ${INSTALLED_VER}"
fi

# ── 완료 ──────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "설치 완료!"
echo ""
echo "  다음 단계:"
echo "  1. Claude Code를 재시작하세요"
echo "  2. 채팅창에 /mcp 입력 → MCP 목록과 연결 상태 확인"
echo ""
if [[ -z "${ENV_FILE}" ]]; then
  warn "API 키가 비어 있습니다. 팀 키 파일을 받으셨다면:"
  echo "  bash ~/ypstack/scripts/install-stats-pack.sh --env-file ~/team-keys.env"
  echo ""
fi
echo "  문의: 유진아빠 (jaemyny@weolbu.com)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
