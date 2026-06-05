#!/usr/bin/env node
// launcher_node.js — ypstack Windows 플러그인 Node.js MCP 서버 런처
//
// Claude Code 플러그인에서 호출됩니다.
//   node launcher_node.js <mcp-name>
//
// ~/ypstack/<mcp-name>/server.js 를 child_process 로 실행합니다.

const { spawnSync } = require("child_process");
const path = require("path");
const os = require("os");
const fs = require("fs");

const mcpName = process.argv[2];
if (!mcpName) {
  process.stderr.write("[ypstack] 사용법: launcher_node.js <mcp-name>\n");
  process.exit(1);
}

const repo = path.join(os.homedir(), "ypstack");
const server = path.join(repo, mcpName, "server.js");

if (!fs.existsSync(repo)) {
  process.stderr.write(
    "[ypstack] 저장소가 없습니다.\n  setup.bat 을 먼저 실행한 뒤 Claude Code 를 재시작하세요.\n"
  );
  process.exit(1);
}

if (!fs.existsSync(server)) {
  process.stderr.write(`[ypstack] 서버 파일을 찾을 수 없습니다: ${server}\n`);
  process.exit(1);
}

// 현재 프로세스를 server.js 로 교체
const result = spawnSync(process.execPath, [server, ...process.argv.slice(3)], {
  stdio: "inherit",
  env: process.env,
});
process.exit(result.status ?? 1);
