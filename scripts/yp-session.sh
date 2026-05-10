#!/usr/bin/env bash
# yp-session — ypstack 모노레포에서 격리된 worktree 기반 작업 세션 시작
#
# 사용법:
#   yp-session.sh <subdir>             # 격리 세션 진입 (worktree 생성/재사용)
#   yp-session.sh list                 # 활성 worktree 목록
#   yp-session.sh clean <subdir>       # worktree 정리
#   yp-session.sh status               # 모든 worktree 의 git status 요약
#
# 동작:
#   1) ~/ypstack-wt/<subdir>/ 에 git worktree 생성 (없으면)
#   2) 브랜치 work/<subdir> 사용 (없으면 main 에서 분기)
#   3) .yp-session-scope 에 subdir 명 기록 → hook 이 편집 범위 강제
#   4) cd 후 `claude --dangerously-skip-permissions` 실행

set -euo pipefail

YPSTACK="$HOME/ypstack"
WT_BASE="$HOME/ypstack-wt"

list_subdirs() {
    cd "$YPSTACK"
    ls -1 | grep -vE '^(\.|README\.md|CLAUDE\.md)$' | sed 's/^/  /'
}

cmd_list() {
    cd "$YPSTACK"
    echo "📂 활성 worktree:"
    git worktree list
}

cmd_status() {
    cd "$YPSTACK"
    while IFS= read -r line; do
        wt_path=$(echo "$line" | awk '{print $1}')
        branch=$(echo "$line" | awk '{print $3}' | tr -d '[]')
        echo "─── $branch @ $wt_path ───"
        if [ -d "$wt_path" ]; then
            git -C "$wt_path" status --short || true
        fi
        echo ""
    done < <(git worktree list)
}

cmd_clean() {
    local subdir="${1:-}"
    if [ -z "$subdir" ]; then
        echo "사용법: yp-session.sh clean <subdir>"
        exit 1
    fi
    cd "$YPSTACK"
    local wt_path="$WT_BASE/$subdir"
    if [ ! -d "$wt_path" ]; then
        echo "❌ worktree 가 없습니다: $wt_path"
        exit 1
    fi
    if [ -n "$(git -C "$wt_path" status --porcelain)" ]; then
        echo "⚠️  worktree '$subdir' 에 미커밋 변경이 있습니다:"
        git -C "$wt_path" status --short
        echo ""
        read -r -p "그래도 삭제하시겠어요? (yes/no): " ans
        [ "$ans" = "yes" ] || { echo "취소됨"; exit 0; }
    fi
    git worktree remove "$wt_path" --force
    git branch -D "work/$subdir" 2>/dev/null || true
    echo "✅ worktree '$subdir' 정리 완료"
    echo "   (origin 의 work/$subdir 브랜치는 그대로. 필요하면 git push origin --delete work/$subdir)"
}

cmd_enter() {
    local subdir="$1"
    local wt_path="$WT_BASE/$subdir"
    local branch="work/$subdir"

    # subdir 검증
    if [ ! -d "$YPSTACK/$subdir" ]; then
        echo "❌ '$subdir' 가 ypstack 안에 없습니다."
        echo ""
        echo "사용 가능한 subdir:"
        list_subdirs
        exit 1
    fi

    mkdir -p "$WT_BASE"

    if [ ! -d "$wt_path" ]; then
        cd "$YPSTACK"
        if git rev-parse --verify "$branch" >/dev/null 2>&1; then
            git worktree add "$wt_path" "$branch"
        else
            git worktree add "$wt_path" -b "$branch" main
        fi
    fi

    cd "$wt_path"
    echo "$subdir" > .yp-session-scope

    cat <<EOF
════════════════════════════════════════════════════════
 ypstack 격리 세션
 ─────────────────────────────────────────────────────
   subdir : $subdir
   branch : $branch
   path   : $wt_path
   scope  : .yp-session-scope (편집은 이 subdir 로 자동 제한)
════════════════════════════════════════════════════════

EOF

    exec claude --dangerously-skip-permissions
}

# 인자 파싱
case "${1:-}" in
    "")
        cat <<EOF
yp-session — ypstack 격리 작업 세션

사용법:
  yp-session.sh <subdir>           # 격리 세션 진입
  yp-session.sh list               # 활성 worktree 목록
  yp-session.sh status             # 모든 worktree 변경 요약
  yp-session.sh clean <subdir>     # worktree 정리

사용 가능한 subdir:
EOF
        list_subdirs
        exit 0
        ;;
    list)    cmd_list ;;
    status)  cmd_status ;;
    clean)   cmd_clean "${2:-}" ;;
    -h|--help)
        head -16 "$0" | tail -15
        ;;
    *)       cmd_enter "$1" ;;
esac
