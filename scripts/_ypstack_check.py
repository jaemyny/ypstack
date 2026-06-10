"""_ypstack_check.py — ypstack MCP 업데이트 및 키 만료 자동 확인 모듈

각 stats-* / kb-price MCP 서버의 mcp = FastMCP(...) 줄 직후에서 호출됩니다.
1일 1회만 실제 확인을 수행하며, 결과는 stderr로 출력합니다.
Claude Code는 stderr 출력을 경고 메시지로 표시합니다.
"""
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

_YPSTACK = Path(os.path.expanduser("~/ypstack"))
_MARKER = Path(os.path.expanduser("~/.config/ypstack/.last_check"))
_VERSION_FILE = _YPSTACK / "scripts" / "VERSION"
_UPDATE_CMD = "git -C ~/ypstack pull 후 Claude Code 에서 설치 프롬프트(scripts/claude-install-prompt.md) 재실행"
_CHECK_INTERVAL_SEC = 86400  # 24시간


def check_once() -> None:
    """서버 시작 시 1일 1회 업데이트·만료 확인. 빠르게 실패해도 무시."""
    if not _YPSTACK.is_dir():
        return
    now = time.time()
    if _MARKER.exists() and now - _MARKER.stat().st_mtime < _CHECK_INTERVAL_SEC:
        return
    try:
        _run_checks()
    except Exception:
        pass
    finally:
        _MARKER.parent.mkdir(parents=True, exist_ok=True)
        _MARKER.touch()


def _parse_version_file():
    if not _VERSION_FILE.exists():
        return None, None
    lines = _VERSION_FILE.read_text().strip().splitlines()
    version = lines[0].strip() if lines else None
    keys_expire = None
    for line in lines:
        if line.startswith("keys_expire:"):
            keys_expire = line.split(":", 1)[1].strip()
    return version, keys_expire


def _run_checks() -> None:
    version, keys_expire = _parse_version_file()

    # ── 1. API 키 만료 경고 ──────────────────────────────────────────────────
    if keys_expire:
        try:
            expire_date = date.fromisoformat(keys_expire)
            days_left = (expire_date - date.today()).days
            if days_left <= 0:
                _warn("⚠️  팀 API 키가 만료됐습니다! 팀 키 갱신 후 업데이트 필요")
                _warn(f"   업데이트: {_UPDATE_CMD}")
            elif days_left <= 30:
                _warn(f"⚠️  팀 API 키 만료 D-{days_left}. 곧 키 갱신이 필요합니다")
                _warn(f"   업데이트: {_UPDATE_CMD}")
        except ValueError:
            pass

    # ── 2. git 원격 업데이트 확인 (3초 타임아웃) ─────────────────────────────
    behind = 0
    try:
        subprocess.run(
            ["git", "-C", str(_YPSTACK), "fetch", "origin", "main", "--quiet"],
            capture_output=True, timeout=3
        )
        r = subprocess.run(
            ["git", "-C", str(_YPSTACK), "rev-list", "HEAD..origin/main", "--count"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0:
            behind = int(r.stdout.strip() or "0")
    except Exception:
        pass

    # ── 3. 업데이트 안내 (git 원격 대비 뒤처짐) ───────────────────────────────
    if behind > 0:
        version_str = version or "?"
        _warn(f"📦 ypstack 업데이트 있음 (최신: {version_str})")
        _warn(f"   업데이트: {_UPDATE_CMD}")


def _warn(msg: str) -> None:
    print(f"[ypstack] {msg}", file=sys.stderr)
