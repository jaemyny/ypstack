#!/usr/bin/env bash
# Layer 2 hook — Edit/Write/NotebookEdit 가 .yp-session-scope 가 정의한
# subdir 안에 있는지 검사. 위반 시 stderr 출력 + exit 2 (Claude Code 가 차단).
#
# 입력: stdin 으로 JSON {tool_name, tool_input:{file_path, ...}, ...}
# 통과: exit 0
# 차단: stderr + exit 2

set -uo pipefail

# stdin JSON 파싱
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

# file_path 가 비었으면 통과 (다른 형태 호출)
[ -z "$FILE_PATH" ] && exit 0

# .yp-session-scope 검색 — cwd 부터 위로
find_scope_file() {
    local dir="$PWD"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/.yp-session-scope" ]; then
            echo "$dir/.yp-session-scope"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

SCOPE_FILE=$(find_scope_file 2>/dev/null) || true

# scope 파일 없으면 통과 (ypstack 외부 작업이거나 scope 미설정)
if [ -z "${SCOPE_FILE:-}" ]; then
    exit 0
fi

SCOPES=$(cat "$SCOPE_FILE" | tr -d '[:space:]')
SCOPE_ROOT=$(dirname "$SCOPE_FILE")
# 심볼릭 링크 해소 (macOS /tmp → /private/tmp 등)
SCOPE_ROOT=$(python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "$SCOPE_ROOT" 2>/dev/null || echo "$SCOPE_ROOT")

# scope 비어있으면 통과
[ -z "$SCOPES" ] && exit 0

# 절대경로 정규화
ABS_FILE=$(python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

# scope 가 콤마로 여러 개 (예: "kb-price-mcp,stats-realty-mcp")
IFS=',' read -ra SCOPE_LIST <<< "$SCOPES"

# scope 안의 파일이면 통과
for s in "${SCOPE_LIST[@]}"; do
    s_trimmed=$(echo "$s" | tr -d '[:space:]')
    [ -z "$s_trimmed" ] && continue
    case "$ABS_FILE" in
        "$SCOPE_ROOT/$s_trimmed"/*|"$SCOPE_ROOT/$s_trimmed")
            exit 0
            ;;
    esac
done

# cross-cutting 파일이면 경고만 (통과)
case "$ABS_FILE" in
    "$SCOPE_ROOT/README.md"|"$SCOPE_ROOT/CLAUDE.md"|"$SCOPE_ROOT/.gitignore")
        echo "ℹ️  cross-cutting 파일 수정: $ABS_FILE (현재 scope: $SCOPES) — 사용자 명시 허락 후 진행하세요." >&2
        exit 0
        ;;
    "$SCOPE_ROOT/docs"/*|"$SCOPE_ROOT/scripts"/*)
        echo "ℹ️  cross-cutting 디렉토리 수정: $ABS_FILE (현재 scope: $SCOPES) — 사용자 명시 허락 후 진행하세요." >&2
        exit 0
        ;;
esac

# 그 외 = 차단
cat >&2 <<EOF
🚫 작업 범위(scope) 위반: 이 세션은 '$SCOPES' 만 작업할 수 있습니다.
   요청된 경로: $ABS_FILE

   허용 영역:
$(for s in "${SCOPE_LIST[@]}"; do
    s_trimmed=$(echo "$s" | tr -d '[:space:]')
    [ -n "$s_trimmed" ] && echo "     - $SCOPE_ROOT/$s_trimmed/"
done)
     - $SCOPE_ROOT/{README.md, CLAUDE.md, .gitignore}  (cross-cutting)
     - $SCOPE_ROOT/{docs, scripts}/                    (cross-cutting)

   다른 subdir 작업이 필요하면 별도 worktree 에서 진행하세요:
     yp-session.sh <other-subdir>

   여러 subdir 를 한 세션에서 다뤄야 한다면 .yp-session-scope 에 콤마로 추가:
     echo "kb-price-mcp,stats-realty-mcp" > .yp-session-scope
EOF
exit 2
