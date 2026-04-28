#!/bin/bash
# realty-data-mcp 자동 설치 스크립트
# 사용법: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_JSON="$HOME/.claude/mcp.json"

echo "======================================"
echo " realty-data-mcp 설치 시작"
echo "======================================"
echo ""
echo " 이 MCP 서버는 Claude Code에서 자연어로"
echo " 한국 부동산/경제 데이터를 조회할 수 있게 합니다."
echo ""
echo " 제공 도구:"
echo "  - 통계청 KOSIS : 인구·가구·지역 통계 검색"
echo "  - 한국은행 ECOS: 기준금리, 경제지표"
echo "  - 국토부 RTMS  : 아파트 매매·전월세 실거래가"
echo ""

# ── 1. Python 확인 ─────────────────────────────────────────
echo "[1/4] Python 확인 중..."
if command -v /opt/homebrew/bin/python3.11 &>/dev/null; then
    PYTHON="/opt/homebrew/bin/python3.11"
    echo "      Python 발견 (Homebrew 3.11): $PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
    echo "      Python 발견: $PYTHON ($($PYTHON --version))"
else
    echo "      오류: Python3가 설치되어 있지 않습니다."
    echo "      https://www.python.org 에서 Python 3.11 이상을 먼저 설치하세요."
    exit 1
fi

# ── 2. 패키지 설치 ─────────────────────────────────────────
echo ""
echo "[2/4] 필요한 패키지 설치 중..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "      완료 (mcp, httpx, pydantic)"

# ── 3. API 키 입력 ─────────────────────────────────────────
echo ""
echo "[3/4] API 키 입력"
echo "      (사용하지 않을 API는 Enter로 건너뛸 수 있습니다)"
echo ""
echo "  ┌─ KOSIS (통계청) ─────────────────────────────────────"
echo "  │  발급: https://kosis.kr/openapi/index/index.jsp"
echo "  │  → 회원가입 → OpenAPI 활용신청 → 'OPEN API 키 발급'"
read -p "  │  KOSIS API 키: " KOSIS_KEY
echo ""
echo "  ┌─ ECOS (한국은행) ─────────────────────────────────────"
echo "  │  발급: https://ecos.bok.or.kr/api/#/DevGuide/TokenSummary"
read -p "  │  ECOS API 키: " ECOS_KEY
echo ""
echo "  ┌─ RTMS (국토부 아파트 실거래가) ───────────────────────"
echo "  │  발급: https://www.data.go.kr → '아파트매매실거래자료' 검색 → 활용신청"
read -p "  │  RTMS API 키: " RTMS_KEY

# ── 4. ~/.claude/mcp.json 업데이트 ─────────────────────────
echo ""
echo "[4/4] Claude Code 설정 파일 업데이트 중..."

mkdir -p "$HOME/.claude"

NEW_ENTRY=$(cat <<ENTRY
    "realty-data": {
      "command": "$PYTHON",
      "args": ["$SCRIPT_DIR/server.py"],
      "env": {
        "KOSIS_API_KEY": "$KOSIS_KEY",
        "ECOS_API_KEY":  "$ECOS_KEY",
        "RTMS_API_KEY":  "$RTMS_KEY"
      }
    }
ENTRY
)

if [ -f "$MCP_JSON" ]; then
    if grep -q '"realty-data"' "$MCP_JSON" 2>/dev/null; then
        echo "      이미 realty-data 설정이 존재합니다."
        echo "      수동으로 $MCP_JSON 을 업데이트해 주세요."
    else
        echo "      ⚠️  기존 ~/.claude/mcp.json 에 항목을 추가하려면"
        echo "         아래 내용을 mcpServers 블록 안에 수동으로 붙여넣으세요:"
        echo ""
        echo "$NEW_ENTRY"
        echo ""
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
echo " 설치 완료!"
echo "======================================"
echo ""
echo " 다음 단계:"
echo "  1. Claude Code를 완전히 종료 후 재시작"
echo "  2. 아무 대화창에서 아래처럼 요청해보세요:"
echo ""
echo "  예시 질문:"
echo "    '서울 강남구 2024년 1월 아파트 매매 실거래가 조회해줘'"
echo "    '한국은행 기준금리 2024년 추이 알려줘'"
echo "    '서울시 25개구별 세대수 현황 보여줘'"
echo ""
