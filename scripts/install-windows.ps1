# ypstack 부동산 통계 MCP 자동 설치 스크립트 (Windows)
# 실행 방법: install-windows.bat 을 더블클릭하세요.
#
# 자동으로 처리합니다:
#   1. Python / Git 설치 확인
#   2. 저장소 다운로드 → C:\Users\사용자명\ypstack\
#   3. Python 패키지 설치
#   4. Claude Code 설정 파일 자동 생성 (~/.claude/mcp.json)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function OK  ($m) { Write-Host "  [완료] $m" -ForegroundColor Green }
function GO  ($m) { Write-Host "  [진행] $m" -ForegroundColor Cyan }
function WARN($m) { Write-Host "  [주의] $m" -ForegroundColor Yellow }
function FAIL($m) { Write-Host "  [오류] $m" -ForegroundColor Red }
function LINE     { Write-Host ("=" * 54) -ForegroundColor DarkGray }

LINE
Write-Host "  ypstack 부동산 통계 MCP 자동 설치" -ForegroundColor White
Write-Host "  (부동산·금융·인구·상권·교통 등 10종)" -ForegroundColor DarkGray
LINE
Write-Host ""

# ── 1. Python 확인 ───────────────────────────────────────
GO "Python 설치 확인 중..."
$pyOk = $false
try {
    $v = & python --version 2>&1
    if ($LASTEXITCODE -eq 0) { OK "Python 확인: $v"; $pyOk = $true }
} catch {}

if (-not $pyOk) {
    FAIL "Python 이 설치되어 있지 않습니다."
    Write-Host ""
    Write-Host "  ▶ Python 설치 방법" -ForegroundColor Yellow
    Write-Host "    1) 인터넷 브라우저에서 아래 주소로 이동"
    Write-Host "       https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "    2) 파란색 'Download Python 3.x' 버튼 클릭"
    Write-Host "    3) 설치 파일 실행 시 첫 화면에서" -ForegroundColor Yellow
    Write-Host "       'Add Python to PATH' 체크박스를 반드시 체크!" -ForegroundColor Red
    Write-Host "    4) Install Now 클릭해서 설치 완료"
    Write-Host "    5) 설치 후 이 창 닫고 install-windows.bat 다시 실행"
    Write-Host ""
    Read-Host "엔터를 누르면 창이 닫힙니다"
    exit 1
}

# ── 2. Git 확인 ──────────────────────────────────────────
GO "Git 설치 확인 중..."
$gitOk = $false
try {
    $v = & git --version 2>&1
    if ($LASTEXITCODE -eq 0) { OK "Git 확인: $v"; $gitOk = $true }
} catch {}

if (-not $gitOk) {
    FAIL "Git 이 설치되어 있지 않습니다."
    Write-Host ""
    Write-Host "  ▶ Git 설치 방법" -ForegroundColor Yellow
    Write-Host "    1) 인터넷 브라우저에서 아래 주소로 이동"
    Write-Host "       https://git-scm.com/download/win" -ForegroundColor Cyan
    Write-Host "    2) 자동으로 다운로드 시작 — 다운로드된 파일 실행"
    Write-Host "    3) 설치 중 모든 화면에서 Next 만 눌러도 됩니다"
    Write-Host "    4) 설치 후 이 창 닫고 install-windows.bat 다시 실행"
    Write-Host ""
    Read-Host "엔터를 누르면 창이 닫힙니다"
    exit 1
}

# ── 3. 저장소 클론 / 업데이트 ────────────────────────────
Write-Host ""
$ypstack = Join-Path $env:USERPROFILE "ypstack"
if (Test-Path (Join-Path $ypstack ".git")) {
    GO "저장소 최신 버전으로 업데이트 중..."
    & git -C $ypstack pull --quiet --ff-only 2>&1 | Out-Null
    OK "저장소 업데이트 완료"
} else {
    GO "저장소 처음 다운로드 중... (1~3분 소요, 잠시 기다려주세요)"
    & git clone https://github.com/jaemyny/ypstack.git $ypstack 2>&1 | Out-Null
    OK "저장소 다운로드 완료: $ypstack"
}

# ── 4. Python 패키지 설치 ────────────────────────────────
Write-Host ""
GO "필요한 Python 패키지 설치 중... (1~2분 소요)"
$mcpList = @(
    "stats-realty-mcp","stats-mcp","stats-finance-mcp","stats-job-mcp",
    "stats-biz-mcp","stats-transit-mcp","stats-edu-mcp","stats-env-mcp","kb-price-mcp"
)
foreach ($mcp in $mcpList) {
    $req = Join-Path $ypstack "$mcp\requirements.txt"
    if (Test-Path $req) {
        & python -m pip install -q -r $req 2>&1 | Out-Null
        OK $mcp
    }
}

# ── 4-b. stats-pubprice-mcp (Node.js) ────────────────────
$nodeOk = $false
try {
    $v = & node --version 2>&1
    if ($LASTEXITCODE -eq 0) { OK "Node.js 확인: $v"; $nodeOk = $true }
} catch {}

if (-not $nodeOk) {
    WARN "Node.js 없음 — stats-pubprice-mcp(공시가격) 건너뜁니다."
    WARN "Node.js 설치: winget install OpenJS.NodeJS.LTS 실행 후 bat 다시 실행"
} else {
    $pubpriceReq = Join-Path $ypstack "stats-pubprice-mcp\package.json"
    if (Test-Path $pubpriceReq) {
        $pubpriceDir = Join-Path $ypstack "stats-pubprice-mcp"
        Set-Location $pubpriceDir
        & npm install --silent 2>&1 | Out-Null
        Set-Location $PSScriptRoot
        OK "stats-pubprice-mcp"
    }
}

# ── 5. 설정 파일 생성 (Claude Desktop + Claude Code) ─────
Write-Host ""
GO "Claude Desktop / Claude Code 설정 파일 생성 중..."

$ys = $ypstack.Replace("\", "/")
$tmpPy = Join-Path $env:TEMP "ypstack_mcp_setup.py"

$pyCode = @'
import json, os, sys

ypstack  = sys.argv[1]
node_ok  = sys.argv[2] == "true"

# 설정을 저장할 두 경로 (Claude Desktop + Claude Code)
targets = [
    os.path.join(os.environ.get("APPDATA", ""), "Roaming", "Claude", "claude_desktop_config.json"),
    os.path.join(os.path.expanduser("~"), ".claude", "mcp.json"),
]

new_servers = {
    "stats-realty": {
        "command": "python",
        "args": [f"{ypstack}/stats-realty-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
            "REB_API_KEY":    "a32cd4fb1ae6467a8870277d0a9d6386",
            "KOSIS_API_KEY":  "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
        },
    },
    "kb-price": {
        "command": "python",
        "args": [f"{ypstack}/kb-price-mcp/server.py"],
    },
    "stats": {
        "command": "python",
        "args": [f"{ypstack}/stats-mcp/server.py"],
        "env": {
            "KOSIS_API_KEY":        "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
            "SGIS_CONSUMER_KEY":    "f18615e1d50242f1a3df",
            "SGIS_CONSUMER_SECRET": "f4bef8ce9c30440ca904",
            "SEOUL_API_KEY":        "67676975446a6165313032546e4a466e",
            "GG_API_KEY":           "b4c53be41a034da98e8093f138a700d8",
        },
    },
    "stats-finance": {
        "command": "python",
        "args": [f"{ypstack}/stats-finance-mcp/server.py"],
        "env": {
            "ECOS_API_KEY": "WN3E49K1TCIX2YIIVBW4",
            "DART_API_KEY": "660ed63c5aecc383b9e03168595fd8bcbca3858f",
        },
    },
    "stats-job": {
        "command": "python",
        "args": [f"{ypstack}/stats-job-mcp/server.py"],
        "env": {
            "KOSIS_API_KEY":  "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
            "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
        },
    },
    "stats-biz": {
        "command": "python",
        "args": [f"{ypstack}/stats-biz-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
            "SEOUL_API_KEY":  "67676975446a6165313032546e4a466e",
            "REB_API_KEY":    "a32cd4fb1ae6467a8870277d0a9d6386",
        },
    },
    "stats-transit": {
        "command": "python",
        "args": [f"{ypstack}/stats-transit-mcp/server.py"],
        "env": {
            "SEOUL_API_KEY": "67676975446a6165313032546e4a466e",
            "KOSIS_API_KEY": "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
        },
    },
    "stats-edu": {
        "command": "python",
        "args": [f"{ypstack}/stats-edu-mcp/server.py"],
        "env": {
            "NEIS_API_KEY": "3f9764de834045c7afb05a92acb90b18",
        },
    },
    "stats-env": {
        "command": "python",
        "args": [f"{ypstack}/stats-env-mcp/server.py"],
        "env": {
            "DATA_GO_KR_KEY": "5645096c13aff5acb7516b66709e58a5702796f0afe9df41e486cd02e0148830",
            "SEOUL_API_KEY":  "67676975446a6165313032546e4a466e",
            "KOSIS_API_KEY":  "Y2UwMDE5MzU4MTdhOWIzY2E2NjU3NDQ5Nzk1MzY2M2Q=",
        },
    },
}

if node_ok:
    new_servers["stats-pubprice"] = {
        "command": "node",
        "args": [f"{ypstack}/stats-pubprice-mcp/server.js"],
        "env": {
            "VWORLD_API_KEY": "ED4B0E1F-6D78-3D81-9301-8471900DD71F",
            "VWORLD_DOMAIN":  "localhost",
        },
    }

for path in targets:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.setdefault("mcpServers", {})
    existing["mcpServers"].update(new_servers)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"저장 완료: {path}")
'@

$pyCode | Set-Content -Path $tmpPy -Encoding UTF8
& python $tmpPy $ys $nodeOk.ToString().ToLower()
Remove-Item $tmpPy -ErrorAction SilentlyContinue

OK "설정 파일 생성 완료 (Claude Desktop + Claude Code)"

# ── 완료 ─────────────────────────────────────────────────
Write-Host ""
LINE
Write-Host "  설치 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "  이제 아래 2단계만 하시면 됩니다:" -ForegroundColor White
Write-Host ""
Write-Host "  1) Claude Desktop / Claude Code 앱을 완전히 종료 후 다시 시작" -ForegroundColor White
Write-Host "     (작업표시줄에서 우클릭 -> 닫기 또는 완전 종료)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2) 채팅창에 아래 입력 후 연결 확인" -ForegroundColor White
Write-Host "     /mcp" -ForegroundColor Cyan
Write-Host ""
Write-Host "  stats-realty, stats, stats-finance 등이" -ForegroundColor DarkGray
Write-Host "  connected 로 표시되면 사용 준비 완료입니다." -ForegroundColor DarkGray
LINE
Write-Host ""
Read-Host "엔터를 누르면 창이 닫힙니다"
