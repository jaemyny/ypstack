# ypstack

유진아빠의 커스텀 Claude Code 확장 모음.
[gstack](https://github.com/garrytan/gstack)(Garry Tan)에서 영감을 받아 만든 개인 스킬셋.

---

## 포함된 도구

### 슬래시 커맨드 (Slash Commands)

Claude Code에서 `/yp-` 접두사로 호출하는 커맨드입니다.

| 스킬 | 설명 |
|------|------|
| [`/yp-dev-log`](./yp-dev-log) | Phase 완료 시 Confluence용 Dev Log 자동 생성 + 자동 게시 |

### MCP 서버 (MCP Servers)

Claude Code에 연결해 두면 자연어로 외부 서비스를 조작할 수 있는 확장 도구입니다.

#### 한국 데이터 통합 스택 (stats-* MCPs)

부동산·금융·인구·고용·상권·교통·교육·환경 데이터를 도메인별로 분리한 8개의 MCP 서버입니다.  
각 MCP는 독립 설치 가능하며, Claude가 여러 MCP를 순차 호출해 교차 분석도 수행합니다.

| MCP | 설명 | 도구 수 | 설치 가이드 |
|-----|------|:-------:|------------|
| [`stats-realty-mcp`](./stats-realty-mcp/INSTALL.md) | **부동산 거래·단지** — 아파트 매매·전월세·분양권 실거래, 단지검색, 주택인허가, 가격지수(부동산원·KB) | 9 | [INSTALL.md](./stats-realty-mcp/INSTALL.md) |
| [`stats-mcp`](./stats-mcp/INSTALL.md) | **인구·가구·지역통계** — KOSIS 인구·세대·가구주연령 통계, SGIS 지역통계, 서울 생활인구, 경기 통계 | 8 | [INSTALL.md](./stats-mcp/INSTALL.md) |
| [`stats-finance-mcp`](./stats-finance-mcp/INSTALL.md) | **금융·경제·기업공시** — 한국은행 금리·GDP·CPI·환율, 주담대금리, OpenDART 기업공시·재무제표 | 7 | [INSTALL.md](./stats-finance-mcp/INSTALL.md) |
| [`stats-job-mcp`](./stats-job-mcp/INSTALL.md) | **고용·임금·사업체** — 지역별 취업자·임금·사업체 수, 국민연금 가입자 통계 | 5 | [INSTALL.md](./stats-job-mcp/INSTALL.md) |
| [`stats-biz-mcp`](./stats-biz-mcp/INSTALL.md) | **상권·상가·유동인구** — 소상공인 상가정보, 상권 통계, 서울 유동인구, 상업용 부동산 임대료 | 5 | [INSTALL.md](./stats-biz-mcp/INSTALL.md) |
| [`stats-transit-mcp`](./stats-transit-mcp/INSTALL.md) | **교통·대중교통** — 지하철 승하차·실시간 도착, 버스노선, KOSIS 교통통계 | 5 | [INSTALL.md](./stats-transit-mcp/INSTALL.md) |
| [`stats-edu-mcp`](./stats-edu-mcp/INSTALL.md) | **교육·학교·학원** — NEIS 학교·학원 현황, 학생 수, 스쿨존 정보 | 5 | [INSTALL.md](./stats-edu-mcp/INSTALL.md) |
| [`stats-env-mcp`](./stats-env-mcp/INSTALL.md) | **환경·대기·공원** — 에어코리아 실시간 대기질, 측정소, 서울 공원 목록, 환경통계 | 5 | [INSTALL.md](./stats-env-mcp/INSTALL.md) |

#### 기타 MCP

| MCP | 설명 | 설치 가이드 |
|-----|------|------------|
| [`confluence-label-mcp`](./confluence-label-mcp/INSTALL.md) | **Confluence 레이블 관리** — Confluence 페이지에 레이블(태그)을 추가·조회·삭제 | [INSTALL.md](./confluence-label-mcp/INSTALL.md) |
| [`realty-data-mcp`](./realty-data-mcp/INSTALL.md) | *(구버전)* **한국 부동산·경제 데이터** — stats-* MCPs로 대체됨 | [INSTALL.md](./realty-data-mcp/INSTALL.md) |

---

## 슬래시 커맨드 설치 방법

### 전체 ypstack 설치

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
```

### `yp-dev-log`만 설치

```bash
git clone https://github.com/jaemyny/ypstack.git /tmp/ypstack
mkdir -p ~/ypstack
cp -r /tmp/ypstack/yp-dev-log ~/ypstack/yp-dev-log
rm -rf /tmp/ypstack
```

### 업데이트

```bash
cd ~/ypstack && git pull
```

설치 후 Claude Code를 재시작해야 스킬이 인식됩니다.

---

## MCP 서버 설치 방법

각 MCP 서버는 별도 설치 과정이 필요합니다. 각 폴더의 `INSTALL.md`를 참고하세요.

### stats-* MCP 전체 설치

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack

# 원하는 MCP만 골라서 설치 (각각 독립 실행)
bash ~/ypstack/stats-realty-mcp/setup.sh   # 부동산 거래·단지
bash ~/ypstack/stats-mcp/setup.sh          # 인구·가구·지역통계
bash ~/ypstack/stats-finance-mcp/setup.sh  # 금융·경제·기업공시
bash ~/ypstack/stats-job-mcp/setup.sh      # 고용·임금·사업체
bash ~/ypstack/stats-biz-mcp/setup.sh      # 상권·상가·유동인구
bash ~/ypstack/stats-transit-mcp/setup.sh  # 교통·대중교통
bash ~/ypstack/stats-edu-mcp/setup.sh      # 교육·학교·학원
bash ~/ypstack/stats-env-mcp/setup.sh      # 환경·대기·공원
```

> 필요한 MCP만 선택해서 설치하면 됩니다. API 키가 없는 항목은 Enter로 건너뛸 수 있습니다.

### Confluence 레이블 관리 MCP (`confluence-label-mcp`) 빠른 시작

```bash
git clone https://github.com/jaemyny/ypstack.git ~/ypstack
bash ~/ypstack/confluence-label-mcp/setup.sh
```

→ 자세한 내용: [confluence-label-mcp/INSTALL.md](./confluence-label-mcp/INSTALL.md)

## 환경 변수 (전역)

각 스킬이 외부 API를 호출할 때 사용하는 토큰/시크릿은 전역 위치에 둡니다:

```bash
mkdir -p ~/.config/ypstack && chmod 700 ~/.config/ypstack
# ~/.config/ypstack/.env 에 필요한 환경 변수 기록
chmod 600 ~/.config/ypstack/.env
```

구체적인 필요 환경 변수는 각 스킬의 `SKILL.md` 참조.

## 스킬셋 관리

- **gstack**: `~/.claude/skills/gstack/` (Garry Tan, `gstack-upgrade`로 업데이트)
- **ypstack**: `~/.claude/skills/ypstack/` (유진아빠 자체 관리, `git pull`로 업데이트)

두 스킬셋은 독립적이며 충돌하지 않습니다.

## 라이선스

MIT
