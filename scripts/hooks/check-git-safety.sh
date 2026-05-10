#!/usr/bin/env bash
# Layer 2 hook — 위험한 git 명령 차단.
# 다른 세션의 변경을 휩쓸 수 있는 패턴을 OS 수준에서 거부한다.
#
# 차단 대상:
#   - git add .       / -A / --all
#   - git commit -a   / -am / --all
# 입력: stdin 으로 JSON {tool_name:"Bash", tool_input:{command, ...}}

set -uo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    pass
" 2>/dev/null)

[ -z "$CMD" ] && exit 0

# 한 줄에 여러 명령(;, &&, ||, |) 으로 우회 못 하도록 줄 단위가 아닌 문자열 전체 검사

# 1) git add . / -A / --all
if [[ "$CMD" =~ (^|[[:space:]\;\|\&])git[[:space:]]+add[[:space:]]+(\.|-A|--all)([[:space:]]|$) ]]; then
    cat >&2 <<'EOF'
🚫 위험한 git 명령 차단: `git add . / -A / --all`
   다른 세션의 미커밋 변경까지 휩쓸어 stage 합니다.

   대안: 명시적 파일 단위로
     git add path/to/file1 path/to/file2

   현재 변경 확인:
     git status --short
EOF
    exit 2
fi

# 2) git commit -a / -am / --all (단, --amend 는 통과)
# -a 가 들어있는 짧은 옵션을 잡되 --amend 는 제외
if [[ "$CMD" =~ (^|[[:space:]\;\|\&])git[[:space:]]+commit[[:space:]]+(--all([[:space:]]|$)|-[a-zA-Z]*a[a-zA-Z]*([[:space:]]|$)) ]] && \
   ! [[ "$CMD" =~ --amend ]]; then
    # 추가 정밀 검사: -a 가 단독 또는 -am, -ma 등에 포함된 경우만 매칭
    if [[ "$CMD" =~ (^|[[:space:]])git[[:space:]]+commit[[:space:]]+(-[a-zA-Z]*a[a-zA-Z]*|--all)([[:space:]]|$) ]]; then
        cat >&2 <<'EOF'
🚫 위험한 git 명령 차단: `git commit -a / -am / --all`
   tracked 파일을 모두 자동 stage 한 뒤 커밋합니다.
   다른 세션의 변경까지 같이 들어갈 수 있어 차단됩니다.

   대안: 명시적 stage 후 일반 commit
     git add <file1> <file2>
     git commit -m "..."
EOF
        exit 2
    fi
fi

exit 0
