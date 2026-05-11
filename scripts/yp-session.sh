#!/usr/bin/env bash
# yp-session — ypstack 모노레포에서 격리된 worktree 기반 작업 세션 시작
#
# 사용법:
#   yp-session.sh <subdir>             # 단일 subdir 격리 세션
#   yp-session.sh <group>              # 그룹 격리 세션 (멀티 subdir)
#   yp-session.sh list                 # 활성 worktree 목록
#   yp-session.sh status               # 모든 worktree 의 git status 요약
#   yp-session.sh clean <name>         # worktree 정리
#
# 사전 정의 그룹:
#   stats   = 모든 stats-* MCP (자동 glob)
#   realty  = stats-realty-mcp + kb-price-mcp (부동산 작업)
#   all     = 모든 MCP (전체 점검용, 신중히 사용)
#
# 동작 (단일 또는 그룹 모두 동일):
#   1) ~/ypstack-wt/<name>/ 에 git worktree 생성 (없으면)
#   2) 브랜치 work/<name> 사용 (없으면 main 에서 분기)
#   3) .yp-session-scope 에 작업 범위 기록 (그룹이면 콤마로 여러 subdir)
#   4) `claude --dangerously-skip-permissions` 실행

set -euo pipefail

YPSTACK="$HOME/ypstack"
WT_BASE="$HOME/ypstack-wt"

# ─── 그룹 정의 ─────────────────────────────────────────────────────
# 그룹명 → 콤마로 나열된 subdir 목록
resolve_group() {
    local name="$1"
    case "$name" in
        stats)
            # 자동 glob: stats-* 패턴
            ls -d "$YPSTACK"/stats* 2>/dev/null | xargs -n1 basename | sort | tr '\n' ',' | sed 's/,$//'
            ;;
        realty)
            echo "stats-realty-mcp,kb-price-mcp"
            ;;
        all)
            # 모든 MCP subdir (skill·docs·scripts 제외)
            ls -1 "$YPSTACK" | grep -E '\-mcp$' | sort | tr '\n' ',' | sed 's/,$//'
            ;;
        *)
            return 1
            ;;
    esac
}

is_group() {
    case "$1" in
        stats|realty|all) return 0 ;;
        *) return 1 ;;
    esac
}

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
    local name="$1"
    local wt_path="$WT_BASE/$name"
    local branch="work/$name"
    local scope
    local is_grp=false

    # 그룹 vs 단일 subdir 판별
    if is_group "$name"; then
        is_grp=true
        scope=$(resolve_group "$name")
        if [ -z "$scope" ]; then
            echo "❌ 그룹 '$name' 에 해당하는 subdir 가 없습니다."
            exit 1
        fi
    elif [ -d "$YPSTACK/$name" ]; then
        scope="$name"
    else
        echo "❌ '$name' 가 ypstack 안에 없고 그룹명도 아닙니다."
        echo ""
        echo "사용 가능한 subdir:"
        list_subdirs
        echo ""
        echo "사용 가능한 그룹:"
        echo "  stats   — 모든 stats-* MCP"
        echo "  realty  — stats-realty-mcp + kb-price-mcp"
        echo "  all     — 모든 MCP (전체 점검용)"
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
    echo "$scope" > .yp-session-scope

    if $is_grp; then
        cat <<EOF
════════════════════════════════════════════════════════
 ypstack 그룹 격리 세션
 ─────────────────────────────────────────────────────
   group   : $name
   subdirs : $scope
   branch  : $branch
   path    : $wt_path
   scope   : .yp-session-scope (편집은 위 subdir 들로 제한)
════════════════════════════════════════════════════════

 ⚠️  여러 MCP 를 한 세션에서 작업합니다. 커밋은 가급적
     subdir 단위로 분리하세요:
       fix(stats-realty-mcp): ...
       fix(stats-biz-mcp): ...

EOF
    else
        cat <<EOF
════════════════════════════════════════════════════════
 ypstack 격리 세션
 ─────────────────────────────────────────────────────
   subdir : $name
   branch : $branch
   path   : $wt_path
   scope  : .yp-session-scope (편집은 이 subdir 로 자동 제한)
════════════════════════════════════════════════════════

EOF
    fi

    exec claude --dangerously-skip-permissions
}

# 인자 파싱
case "${1:-}" in
    "")
        cat <<EOF
yp-session — ypstack 격리 작업 세션

사용법:
  yp-session.sh <subdir>           # 단일 subdir 격리 세션
  yp-session.sh <group>            # 그룹 격리 세션 (멀티 subdir)
  yp-session.sh list               # 활성 worktree 목록
  yp-session.sh status             # 모든 worktree 변경 요약
  yp-session.sh clean <name>       # worktree 정리

사전 정의 그룹:
  stats   — 모든 stats-* MCP $(resolve_group stats | tr ',' ' ' | wc -w | tr -d ' ')개
  realty  — stats-realty-mcp + kb-price-mcp
  all     — 모든 MCP

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
