---
name: yp-dev-log
description: |
  Phase 완료 시 Confluence용 Dev Log를 자동 생성합니다. 대화 이력 + git 로그를 기반으로
  비개발자도 이해할 수 있는 개발 회고 문서를 작성합니다. 사용자가 "dev log", "개발 로그",
  "Phase 회고", "/yp-dev-log"를 요청할 때 호출하세요. (ypstack, by 유진아빠)
---

# /yp-dev-log — AI Dev Log 자동 생성

## 설치 및 설정

### 설치 (최초 1회)

이 스킬만 단독으로 설치할 수 있습니다:
```bash
mkdir -p ~/.claude/skills/ypstack
cp -r yp-dev-log ~/.claude/skills/ypstack/yp-dev-log
```

또는 ypstack 전체를 설치:
```bash
git clone [ypstack 레포 URL] ~/.claude/skills/ypstack
```

### Confluence 자동 게시 설정 (선택사항)

Dev Log를 Confluence에 자동 게시하려면 API 토큰이 필요합니다. 설정하지 않으면 마크다운 파일만 생성됩니다.

**1단계: Confluence API 토큰 발급**
1. https://id.atlassian.com/manage-profile/security/api-tokens 접속
2. "Create API token" 클릭
3. 라벨: "Claude Code Dev Log" 입력
4. 생성된 토큰을 복사

**2단계: 환경 변수 등록 (전역 1회)**

전역 설정 파일 `~/.config/ypstack/.env`에 아래 3줄 기록. 이 파일은 모든 프로젝트에서 공유된다:
```bash
mkdir -p ~/.config/ypstack && chmod 700 ~/.config/ypstack
cat > ~/.config/ypstack/.env <<'EOF'
CONFLUENCE_BASE_URL=https://weolbu-company.atlassian.net
CONFLUENCE_USER_EMAIL=본인의_weolbu_이메일
CONFLUENCE_API_TOKEN=발급받은_토큰
EOF
chmod 600 ~/.config/ypstack/.env
```

**로드 우선순위 (나중 것이 앞 것을 덮어씀):**
1. `~/.config/ypstack/.env` — 전역, 모든 프로젝트 공유 (권장)
2. `<프로젝트>/backend/.env` — 프로젝트별 오버라이드 (선택)
3. `<프로젝트>/.env` — 프로젝트 루트 오버라이드 (선택)
4. 셸 환경 변수 (`export CONFLUENCE_API_TOKEN=...`) — 최상위 우선

**프로젝트별 오버라이드가 필요한 경우**: 특정 프로젝트만 다른 Confluence 사이트/계정을 써야 할 때, 해당 프로젝트의 `.env`에 동일 키를 써서 덮어쓰기.

**동작 규칙:**
- 3개 변수가 모두 설정되면 자동 게시
- 하나라도 비어 있거나 토큰이 플레이스홀더면 "Confluence 토큰이 설정되지 않았습니다. 마크다운 파일로 생성합니다." 메시지 표시 후 마크다운 파일만 생성 (게시 스킵)

**보안:**
- `~/.config/ypstack/.env`는 홈 디렉토리 아래이므로 git 저장소에 커밋될 위험 없음
- 토큰 파일 권한은 `600`, 디렉토리는 `700`으로 제한

---

## 실행 순서

### Step 1: 프로젝트 정보 수집 (자동)

1. CLAUDE.md를 읽고 프로젝트 현재 상태 파악
2. git log 분석:
   - 이번 Phase의 커밋 이력 (feat/fix/docs/ci/chore 분류)
   - 변경 파일, 삽입/삭제 LOC 통계
   - 커밋 시간대 분포
   - AI-assisted 커밋 비율 (Co-Authored-By 트레일러 기준)
3. 참조 가능한 문서 확인:
   - HANDOFF_*.md (인수인계 문서)
   - PRD_*.md (기획 문서)
   - eng-review 리포트 (~/.gstack/projects/*/\*eng-review\*.md)
   - retro 결과 (~/.gstack/projects/*/\*retro\*.md 또는 learnings.jsonl)

### Step 2: 사용자에게 최소 정보 질문 (3개만)

아래 3개를 한 번에 물어보고 답변을 받는다:
1. "이번 Phase의 이름과 기간은?" (예: Phase 7, 4/10~4/17)
2. "작성자 닉네임과 소속팀은?" (예: 유진아빠, 프롭테크팀)
3. "Confluence 상위 페이지 ID는?" (기본값: 2095776641)

### Step 3: Dev Log 문서 생성

아래 템플릿에 맞춰 Markdown 문서를 생성한다.

작성 규칙:
- 독자는 비개발자. 기술 용어는 반드시 괄호 안에 쉬운 말로 풀어서 설명
- 톤: 간결체. "~했다. 이유는 ~때문이다."
- 대화 이력에서 추출 불가한 정보는 [💬 작성자 확인 필요: ___]로 표시
- 작성자가 빈칸만 채우면 완성되도록 만든다
- 분량: A4 3~4페이지
- Confluence 마크다운 호환 형식으로 작성

---

## Dev Log 템플릿

### 1. 한 장 요약 (Executive Summary)

- 앱/도구 이름: (CLAUDE.md에서 추출)
- 이번 Phase: (Step 2에서 입력받음)
- 기간: [시작일 ~ 종료일, N일] (Step 2에서 입력받음)
- 제작자: [닉네임 / 소속팀] (Step 2에서 입력받음)
- 개발 도구: Claude Code + gstack (AI 페어 프로그래밍)
- 현재 상태: (CLAUDE.md에서 추출: 운영 중 / 베타 테스트 중 / 보관)
- 한 줄 요약: (이번 Phase에서 달성한 것을 한 문장으로. HANDOFF 문서에서 추출)
- 핵심 숫자:

  | 지표 | Before | After |
  |------|--------|-------|
  (git 로그와 CLAUDE.md에서 추출하여 자동 작성. 추출 불가 항목은 💬 표시)

### 2. 왜 만들었나 (Problem → Solution)

- 기존의 고통: (PRD 또는 CLAUDE.md에서 추출. 구체적 시나리오로 서술. "매주 월요일 회의가 끝나면..." 식)
- 이번 Phase의 목표: (PRD에서 추출)
- 달성 여부: [완전 달성 / 부분 달성 / 미달성] + 이유 (HANDOFF 문서의 완료/미완료 항목에서 판단)

### 3. 이번 Phase에서 만든 것 (What We Shipped)

(git log의 feat: 커밋을 기반으로 기능 목록 자동 생성. 사용자 시나리오 형식으로 서술)

기능 N. [기능 이름]
- 사용자 시나리오: "사용자가 ~하면 ~된다"
- Before: (이전에는 어떻게 했는지)
- After: (이제 어떻게 되는지)

### 4. 핵심 의사결정 로그 (Decision Log)

(eng-review 리포트, CLAUDE.md의 기술 결정사항에서 추출)

| # | 결정 사항 | 선택한 것 | 버린 대안 | 선택 이유 |
|---|----------|----------|----------|----------|

### 5. 실패와 삽질 기록 (What Went Wrong)

(git log의 fix: 커밋을 기반으로 자동 생성. hotfix 체인이 있으면 연결하여 서술)

| # | 무엇이 터졌나 | 증상 | 진짜 원인 | 어떻게 찾았나 | 배운 교훈 |
|---|-------------|------|----------|-------------|----------|

💡 "실패 기록이 이 문서에서 가장 가치 있는 부분이다. 다음 사람이 같은 구멍에 빠지지 않게 해주기 때문이다."

### 6. 기술 스택 (사용된 도구들)

(비개발자 설명 + "왜 이것을 골랐는지" 한 줄 추가. CLAUDE.md의 기술 결정사항에서 추출)

| 도구 | 역할 (쉬운 말) | 왜 이것을 골랐나 |
|------|--------------|----------------|

### 7. 사용 방법 (Quick Start)

(README.md 또는 사용 매뉴얼에서 핵심만 추출. 3~5단계로 압축)
⚠️ 주의사항:
📖 상세 매뉴얼 링크: [💬 작성자 확인 필요: 컨플루언스 매뉴얼 링크]

### 8. 개발 과정 통계 (Dev Stats)

(git log에서 자동 계산)

| 지표 | 수치 | 의미 |
|------|------|------|
| 개발 기간 | N일 | (git log의 첫 커밋~마지막 커밋) |
| 코드 변경량 | N회 수정, +N줄/-N줄 | (git log --stat에서 계산) |
| 실제 코딩 시간 | 약 N시간 | (retro 결과 참조, 없으면 세션 수 × 평균 10분으로 추정) |
| AI 활용률 | N% | (Co-Authored-By 트레일러가 있는 커밋 비율) |
| 자동 테스트 | N개 | (pytest 실행 결과 또는 test 파일 수에서 추출) |
| 배포 횟수 | N회+ | (git log에서 deploy/ship 관련 커밋 수) |
| gstack 스킬 사용 | /xxx, /yyy | (learnings.jsonl 또는 CLAUDE.md에서 추출) |

### 9. 알려진 제약과 한계 (Known Limitations)

(CLAUDE.md의 잔존 이슈, HANDOFF 문서의 미완료 항목에서 추출)

### 10. 다음에 할 것 (What's Next)

(HANDOFF 문서의 다음 Phase 권장 작업에서 추출. 한다/안 한다 명확히 구분)

| 우선순위 | 항목 | 다음 Phase에서 하는가? | 이유 |
|---------|------|---------------------|------|

### 11. 나의 회고 (Personal Reflection)

(대화 이력에서 추론 가능한 것은 채우고, 나머지는 💬 표시)

- 이번에 처음 해본 것: (git 로그에서 신규 기술/도구 사용 추출)
- 예상보다 쉬웠던 것: [💬 작성자 확인 필요: ___]
- 예상보다 어려웠던 것: (fix: 커밋 체인에서 가장 오래 걸린 디버깅 추출)
- AI 페어 프로그래밍에서 배운 것: [💬 작성자 확인 필요: ___]
- 다음 Phase에서 다르게 할 것: (retro의 "3 Things to Improve"에서 추출)

💡 "빌더가 가장 빠르게 성장하는 순간은 자기가 뭘 몰랐는지를 인식하는 순간이다."

### 12. 코드 및 문서 위치

- 서비스 URL: (CLAUDE.md에서 추출)
- 코드 저장소: (git remote -v에서 추출)
- 인수인계 문서: (HANDOFF 파일 경로)
- 사용 매뉴얼: [💬 작성자 확인 필요: 컨플루언스 링크]

### 13. 문의 및 담당자

- 담당자: (Step 2에서 입력받은 닉네임)
- 최초 작성일: (오늘 날짜 자동 계산)
- 최종 수정일: (오늘 날짜 자동 계산)

---

## 출력

1. `docs/dev-log-{phase명}-{YYYYMMDD}.md` 파일로 저장
2. `publish_to_confluence.py`를 실행하여 Confluence에 자동 게시 시도
   ```bash
   python3 ~/.claude/skills/ypstack/yp-dev-log/publish_to_confluence.py <생성된_md_경로>
   ```
   - 상위 페이지 ID: `2095776641`
   - 스페이스 ID: `1023181044`
   - 사이트: `weolbu-company.atlassian.net`
   - 제목: 마크다운 첫 번째 `# H1`에서 추출 (없으면 파일명)
3. 스크립트 종료 코드에 따라 안내:
   - **exit 0** — 게시 성공: 페이지 URL 표시
   - **exit 2** — 중복 감지: "이미 존재합니다" + 기존 페이지 URL 표시. 재게시하려면 Confluence에서 해당 페이지 삭제/수정 후 재실행 안내
   - **exit 10** — 환경 변수 미설정: "Confluence 토큰이 설정되지 않았습니다. 마크다운 파일로 생성합니다." 안내. 설정 방법은 이 문서의 "설치 및 설정" 섹션 참조
   - **exit 3** — API 에러: 에러 메시지 + "수동으로 Confluence에 붙여넣으세요" 안내
   - **exit 1** — 파일 없음 등 사용 오류
