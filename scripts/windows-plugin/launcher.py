"""launcher.py — ypstack Windows 플러그인 MCP 서버 런처

Claude Code 플러그인에서 호출됩니다.
  python launcher.py <mcp-name>

~/ypstack/<mcp-name>/server.py 를 현재 Python 프로세스로 대체(exec)합니다.
setup.bat 으로 저장소를 클론하고 패키지를 설치한 뒤 사용하세요.
"""
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("[ypstack] 사용법: launcher.py <mcp-name>", file=sys.stderr)
        sys.exit(1)

    mcp_name = sys.argv[1]
    repo = os.path.join(os.path.expanduser("~"), "ypstack")
    server = os.path.join(repo, mcp_name, "server.py")

    if not os.path.isdir(repo):
        print(
            "[ypstack] 저장소가 없습니다.\n"
            "  setup.bat 을 먼저 실행한 뒤 Claude Code 를 재시작하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.isfile(server):
        print(f"[ypstack] 서버 파일을 찾을 수 없습니다: {server}", file=sys.stderr)
        sys.exit(1)

    # 현재 프로세스를 server.py 로 교체 (stdin/stdout 유지)
    os.execv(sys.executable, [sys.executable, server] + sys.argv[2:])


if __name__ == "__main__":
    main()
