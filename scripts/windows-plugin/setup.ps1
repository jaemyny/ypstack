# setup.ps1 — ypstack 부동산 통계 MCP 설치 (Windows PowerShell)
# 실행 방법: PowerShell 에서 .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "   ypstack 부동산 통계 MCP 설치 (Windows)" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python 확인 ───────────────────────────────────────
try {
    $pyVer = python --version 2>&1
    Write-Host "  ✔  Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  ✗  Python 이 설치되지 않았습니다." -ForegroundColor Red
    Write-Host ""
    Write-Host "  설치 방법:"
    Write-Host "    1. https://www.python.org/downloads/ 접속"
    Write-Host "    2. 'Download Python 3.x' 클릭"
    Write-Host "    3. 설치 시 'Add Python to PATH' 반드시 체크!"
    Write-Host "    4. 설치 완료 후 이 스크립트 다시 실행"
    Read-Host "엔터를 누르면 종료합니다"
    exit 1
}

# ── 2. Git 확인 ──────────────────────────────────────────
try {
    $gitVer = git --version 2>&1
    Write-Host "  ✔  Git:    $gitVer" -ForegroundColor Green
} catch {
    Write-Host "  ✗  Git 이 설치되지 않았습니다." -ForegroundColor Red
    Write-Host ""
    Write-Host "  설치 방법:"
    Write-Host "    1. https://git-scm.com/download/win 접속"
    Write-Host "    2. 다운로드 후 기본 설정으로 설치"
    Write-Host "    3. 설치 완료 후 이 스크립트 다시 실행"
    Read-Host "엔터를 누르면 종료합니다"
    exit 1
}

# ── 3. 저장소 클론 / 업데이트 ────────────────────────────
Write-Host ""
$ypstack = Join-Path $env:USERPROFILE "ypstack"

if (Test-Path (Join-Path $ypstack ".git")) {
    Write-Host "  →  저장소 최신화 중..." -ForegroundColor Blue
    git -C $ypstack pull --quiet --ff-only
    Write-Host "  ✔  업데이트 완료: $ypstack" -ForegroundColor Green
} else {
    Write-Host "  →  저장소 클론 중... (첫 실행 시 1~2분 소요)" -ForegroundColor Blue
    git clone https://github.com/jaemyny/ypstack.git $ypstack
    Write-Host "  ✔  클론 완료: $ypstack" -ForegroundColor Green
}

# ── 4. Python 패키지 설치 ────────────────────────────────
Write-Host ""
Write-Host "  →  Python 패키지 설치 중..." -ForegroundColor Blue

$mcps = @(
    "stats-realty-mcp", "stats-mcp", "stats-finance-mcp",
    "stats-job-mcp", "stats-biz-mcp", "stats-transit-mcp",
    "stats-edu-mcp", "stats-env-mcp", "kb-price-mcp"
)

foreach ($mcp in $mcps) {
    $req = Join-Path $ypstack "$mcp\requirements.txt"
    if (Test-Path $req) {
        python -m pip install -q -r $req
        Write-Host "  ✔  $mcp" -ForegroundColor Green
    } else {
        Write-Host "  ⚠  $mcp : requirements.txt 없음, 건너뜀" -ForegroundColor Yellow
    }
}

# ── 완료 ─────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  ✔  설치 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "  다음 단계:"
Write-Host "  1. Claude Code 설정 열기 (우상단 프로필 아이콘)"
Write-Host "  2. 확장 프로그램 메뉴 클릭"
Write-Host "  3. '압축 해제된 확장 프로그램 설치' 버튼 클릭"
Write-Host "  4. 이 폴더(setup.ps1 이 있는 폴더)를 선택"
Write-Host "  5. Claude Code 재시작 → /mcp 입력해서 확인"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Read-Host "엔터를 누르면 종료합니다"
