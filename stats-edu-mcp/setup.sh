#!/bin/bash
# stats-edu-mcp 자동 설치 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_JSON="$HOME/.claude/mcp.json"

echo "======================================"
echo " stats-edu-mcp 설치 시작"
echo "======================================"
echo ""
echo " 학교·학원·교육통계 (NEIS, KOSIS)"
echo ""

# ── 1. Python 확인 ─────────────────────────────────────────
echo "[1/4] Python 확인 중..."
if command -v /opt/homebrew/bin/python3.11 &>/dev/null; then
    PYTHON="/opt/homebrew/bin/python3.11"
elif command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
else
    echo "오류: Python3가 설치되어 있지 않습니다."
    exit 1
fi
echo "      Python: $PYTHON ($($PYTHON --version))"

# ── 2. 패키지 설치 ─────────────────────────────────────────
echo ""
echo "[2/4] 패키지 설치 중..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "      완료"

# ── 3. API 키 입력 ─────────────────────────────────────────
echo ""
echo "[3/4] API 키 입력 (Enter로 건너뛰기 가능)"
echo ""
echo "  ┌─ NEIS (교육부 교육통계) ───────────────────────────"
echo "  │  발급: https://open.neis.go.kr"
read -p "  │  NEIS API 키: " NEIS_KEY
echo ""
echo "  ┌─ KOSIS (통계청) ───────────────────────────────────"
echo "  │  발급: https://kosis.kr/openapi/index/index.jsp"
read -p "  │  KOSIS API 키: " KOSIS_KEY

# ── 4. mcp.json 업데이트 ───────────────────────────────────
echo ""
echo "[4/4] Claude Code 설정 파일 업데이트 중..."
mkdir -p "$HOME/.claude"

NEW_ENTRY=$(cat <<ENTRY
    "stats-edu": {
      "command": "$PYTHON",
      "args": ["$SCRIPT_DIR/server.py"],
      "env": {
        "NEIS_API_KEY":  "$NEIS_KEY",
        "KOSIS_API_KEY": "$KOSIS_KEY"
      }
    }
ENTRY
)

if [ -f "$MCP_JSON" ]; then
    if grep -q '"stats-edu"' "$MCP_JSON" 2>/dev/null; then
        echo "      이미 stats-edu 설정이 존재합니다."
        echo "      수동으로 $MCP_JSON 을 업데이트해 주세요."
    else
        echo "      ⚠️  기존 ~/.claude/mcp.json 에 아래 내용을 mcpServers 블록 안에 추가하세요:"
        echo ""
        echo "$NEW_ENTRY"
    fi
else
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
$NEW_ENTRY
  }
}
EOF
    echo "      ~/.claude/mcp.json 생성 완료"
fi

echo ""
echo "======================================"
echo " 설치 완료! Claude Code를 재시작하세요."
echo "======================================"
