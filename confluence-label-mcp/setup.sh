#!/bin/bash
# confluence-label-mcp 자동 설치 스크립트
# 사용법: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_JSON="$HOME/.claude/mcp.json"

echo "======================================"
echo " confluence-label-mcp 설치 시작"
echo "======================================"
echo ""

# 1. Python 확인
echo "[1/4] Python 확인 중..."
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
    echo "      Python 발견: $PYTHON"
elif command -v /opt/homebrew/bin/python3.11 &>/dev/null; then
    PYTHON="/opt/homebrew/bin/python3.11"
    echo "      Python 발견 (Homebrew): $PYTHON"
else
    echo "      오류: Python3가 설치되어 있지 않습니다."
    echo "      https://www.python.org 에서 Python을 먼저 설치해 주세요."
    exit 1
fi

# 2. pip 패키지 설치
echo ""
echo "[2/4] 필요한 패키지 설치 중..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "      완료"

# 3. Confluence 정보 입력받기
echo ""
echo "[3/4] Confluence 연결 정보 입력"
echo "      (입력 중 화면에 글자가 보입니다)"
echo ""

read -p "  Confluence URL (예: https://회사명.atlassian.net/wiki): " CONF_URL
read -p "  Atlassian 계정 이메일: " CONF_EMAIL
echo "  API 토큰 발급 방법: https://id.atlassian.com/manage-profile/security/api-tokens"
read -p "  API 토큰 붙여넣기: " CONF_TOKEN

# 4. ~/.claude/mcp.json 생성/업데이트
echo ""
echo "[4/4] Claude Code 설정 파일 업데이트 중..."

mkdir -p "$HOME/.claude"

NEW_ENTRY=$(cat <<EOF
    "confluence-label": {
      "command": "$PYTHON",
      "args": ["$SCRIPT_DIR/server.py"],
      "env": {
        "CONFLUENCE_URL": "$CONF_URL",
        "CONFLUENCE_EMAIL": "$CONF_EMAIL",
        "CONFLUENCE_TOKEN": "$CONF_TOKEN"
      }
    }
EOF
)

if [ -f "$MCP_JSON" ]; then
    # 기존 파일이 있으면 confluence-label이 이미 있는지 확인
    if grep -q '"confluence-label"' "$MCP_JSON" 2>/dev/null; then
        echo "      이미 confluence-label 설정이 존재합니다."
        echo "      수동으로 $MCP_JSON 을 업데이트해 주세요."
    else
        echo "      기존 ~/.claude/mcp.json에 항목 추가..."
        echo "      ⚠️  수동 병합이 필요합니다. 아래 내용을 ~/.claude/mcp.json 의 mcpServers 안에 추가하세요:"
        echo ""
        echo "$NEW_ENTRY"
    fi
else
    # 파일이 없으면 새로 생성
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
echo " 설치 완료!"
echo "======================================"
echo ""
echo " 다음 단계:"
echo "  1. Claude Code를 완전히 종료 후 재시작"
echo "  2. Claude Code에서 아무 프롬프트나 입력"
echo "  3. 좌측 상단 MCP 아이콘에 'confluence-label' 표시되면 성공"
echo ""
echo " 사용 예시:"
echo "  '페이지 2149286590의 레이블을 조회해줘'"
echo "  '페이지 2149286590에 status-verified 레이블을 추가해줘'"
echo ""
