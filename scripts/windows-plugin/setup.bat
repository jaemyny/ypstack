@echo off
chcp 65001 >nul
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   ypstack 부동산 통계 MCP 설치 (Windows)
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: ── 1. Python 확인 ───────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Python 이 설치되지 않았습니다.
    echo.
    echo  설치 방법:
    echo    1. https://www.python.org/downloads/ 접속
    echo    2. "Download Python 3.x" 버튼 클릭
    echo    3. 설치 화면에서 "Add Python to PATH" 반드시 체크 ^!
    echo    4. 설치 완료 후 이 파일 다시 실행
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Python: %%v

:: ── 2. Git 확인 ──────────────────────────────────────────
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Git 이 설치되지 않았습니다.
    echo.
    echo  설치 방법:
    echo    1. https://git-scm.com/download/win 접속
    echo    2. 다운로드 후 기본 설정으로 설치
    echo    3. 설치 완료 후 이 파일 다시 실행
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo   Git:    %%v

:: ── 3. 저장소 클론 / 업데이트 ────────────────────────────
echo.
set YPSTACK=%USERPROFILE%\ypstack
if exist "%YPSTACK%\.git" (
    echo [업데이트] 저장소 최신화 중...
    git -C "%YPSTACK%" pull --quiet --ff-only
    echo   완료: %YPSTACK%
) else (
    echo [클론] 저장소 다운로드 중... (첫 실행 시 1-2분 소요)
    git clone https://github.com/jaemyny/ypstack.git "%YPSTACK%"
    echo   완료: %YPSTACK%
)

:: ── 4. Python 패키지 설치 ────────────────────────────────
echo.
echo [패키지] Python 패키지 설치 중...
set MCPS=stats-realty-mcp stats-mcp stats-finance-mcp stats-job-mcp stats-biz-mcp stats-transit-mcp stats-edu-mcp stats-env-mcp kb-price-mcp

for %%M in (%MCPS%) do (
    if exist "%YPSTACK%\%%M\requirements.txt" (
        python -m pip install -q -r "%YPSTACK%\%%M\requirements.txt"
        echo   완료: %%M
    ) else (
        echo   건너뜀: %%M ^(requirements.txt 없음^)
    )
)

:: ── 완료 ─────────────────────────────────────────────────
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   설치 완료!
echo.
echo   다음 단계:
echo   1. Claude Code 설정 열기 (우상단 프로필 아이콘)
echo   2. 확장 프로그램 메뉴 클릭
echo   3. "압축 해제된 확장 프로그램 설치" 버튼 클릭
echo   4. 이 폴더(setup.bat 이 있는 폴더)를 선택
echo   5. Claude Code 재시작 후 /mcp 입력해서 연결 확인
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
pause
