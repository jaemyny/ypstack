# ypstack 모노레포 작업 규칙 (자동 로드)

이 파일은 cwd 가 `~/ypstack/` 또는 그 worktree(`~/ypstack-wt/*`) 일 때 Claude Code 가 자동으로 컨텍스트에 주입한다. 사용자가 따로 언급하지 않아도 항상 이 규칙을 우선 적용한다.

---

## 1. 모노레포 구조

이 저장소는 여러 MCP / skill 이 공존하는 단일 모노레포다 (gstack 패턴 벤치마킹). 각 subdir 는 독립적으로 개발될 수 있고, **여러 Claude Code 세션이 동시에 다른 subdir 를 작업할 수 있다.**

| subdir | 내용 |
| --- | --- |
| `stats-realty-mcp/` | 부동산 거래·KB 통계·부동산원 지수 |
| `stats-mcp/` | 인구·가구·지역통계 |
| `stats-finance-mcp/` | 한국은행·DART·KOSPI |
| `stats-job-mcp/` | 고용·임금·국민연금 |
| `stats-biz-mcp/` | 상권·소상공인 |
| `stats-transit-mcp/` | 지하철·버스·교통 |
| `stats-edu-mcp/` | 학교·학원·학군 |
| `stats-env-mcp/` | 대기·공원·환경 |
| `kb-price-mcp/` | KB부동산 단지별 시세 (개인용 비공식) |
| `confluence-label-mcp/` | Confluence 라벨 관리 |
| `yp-dev-log/` | dev log 자동 게시 skill |
| `docs/` | 모노레포 차원 문서 (PRD 등) |
| `scripts/` | 모노레포 차원 자동화 스크립트 |

---

## 2. 세션 시작 시 항상 수행

1. **cwd 의 `.yp-session-scope` 파일을 읽는다.**
   - 있으면 그 안의 subdir 명만 이번 세션의 작업 범위(scope)로 인식
   - 없으면 사용자에게 "이 세션은 어느 subdir 를 작업하나요?" 묻고 답을 `.yp-session-scope` 에 작성
2. scope 가 정해지기 전까지는 어떤 Edit/Write/git 도 수행하지 않는다.
3. cwd 가 `~/ypstack-wt/<subdir>/` 형태면 자동으로 `<subdir>` 를 scope 로 간주.

---

## 3. 절대 금지 (hook 이 OS 수준에서 차단)

| 차단 대상 | 이유 | 대안 |
| --- | --- | --- |
| `git add .` / `-A` / `--all` | 다른 세션 변경까지 stage | `git add <specific-file>` |
| `git commit -a` / `-am` / `--all` | tracked 파일 자동 stage | `git add` 후 일반 commit |
| scope 외 subdir 의 Edit/Write | 다른 세션 작업 침범 | 별도 worktree 에서 진행 |

차단되면 stderr 에 안내가 출력되니 그대로 사용자에게 전달하고 대안을 제시한다.

---

## 4. cross-cutting 파일 — 명시 허락 후만

다음은 모든 scope 에서 수정 *가능* 하지만 **사용자 명시 허락** 받은 후에만 한다:

- `README.md`, `CLAUDE.md`, `.gitignore`
- `docs/` 하위 (PRD 등)
- `scripts/` 하위 (자동화 스크립트)

수정 시 변경 사유를 commit 메시지와 PRD 변경이력에 명시.

---

## 5. Git 커밋 규칙

- **명시적 stage 만**: `git add <file1> <file2> ...` (와일드카드·점 사용 금지)
- **scope 안의 파일만 stage**: `git status` 의 다른 subdir 변경은 다른 세션 작업물이므로 무시
- **메시지 prefix 로 subdir 명시**:
  - `feat(kb-price-mcp): 새 단지 검색 도구 추가`
  - `fix(stats-realty-mcp): KB API 차단 우회`
  - `docs: PRD §6 운영가이드 보강` (cross-cutting)
- **push 는 자기 branch 로**: worktree 에 진입했다면 `work/<subdir>` 브랜치에 푸시
  - `git push -u origin work/<subdir>` (최초)
  - 이후 `git push`
- **main 머지는 사용자 명시 요청 후만**

---

## 6. 권장 진입 방식

새 세션은 항상 다음 한 줄로 시작한다:

```bash
~/ypstack/scripts/yp-session.sh <subdir>
```

이 명령이 자동으로:
1. `~/ypstack-wt/<subdir>/` 에 git worktree 생성 (없으면)
2. `work/<subdir>` 브랜치 분기 또는 재사용
3. `.yp-session-scope` 파일 작성
4. `claude --dangerously-skip-permissions` 실행

→ 그 결과 `git status` 가 자기 worktree 만 보여주므로 다른 세션 변경이 시야에서 사라진다 (물리적 격리).

---

## 7. 진행 중 작업이 다른 subdir 에 걸쳐 있을 때

가끔 한 작업이 여러 subdir 를 합쳐서 봐야 할 수도 있다 (예: kb-price-mcp 가 stats-realty-mcp 의 도구를 호출하는 통합 도구). 이 경우:

1. 사용자에게 명시 허락 요청
2. `.yp-session-scope` 에 `,` 로 여러 subdir 나열 (예: `kb-price-mcp,stats-realty-mcp`)
3. hook 이 둘 다 허용

---

## 8. 검증 체크 (세션 도중 의심스러우면)

```bash
# 현재 scope 확인
cat .yp-session-scope

# 현재 worktree 확인
git worktree list

# 다른 worktree 의 작업은 자기 git status 에 안 보여야 함
git status
```
