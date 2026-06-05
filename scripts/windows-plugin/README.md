# ypstack 부동산 통계 MCP — Windows 플러그인

Claude Code 데스크탑 앱(Windows)에서 10개 부동산·통계 MCP를 GUI로 설치하는 확장 프로그램입니다.

---

## 설치 방법

### Step 1. Python 설치 (없는 경우)

1. https://www.python.org/downloads/ 접속
2. "Download Python 3.x" 클릭해서 설치
3. **설치 시 "Add Python to PATH" 반드시 체크**

### Step 2. setup.bat 실행

이 폴더에서 **setup.bat** 을 더블클릭합니다.  
자동으로 처리합니다:
- Git 으로 저장소 클론 → `%USERPROFILE%\ypstack\`
- 9개 MCP Python 패키지 설치 (pip)

PowerShell 사용자는 `setup.ps1` 을 대신 실행해도 됩니다.

### Step 3. 확장 프로그램 설치 (GUI)

1. Claude Code 데스크탑 앱 실행
2. 우상단 프로필 아이콘 → **설정**
3. 왼쪽 메뉴 → **확장 프로그램**
4. **"압축 해제된 확장 프로그램 설치"** 버튼 클릭
5. **이 폴더** (setup.bat 이 있는 폴더) 를 선택
6. Claude Code **재시작**

### Step 4. 연결 확인

Claude Code 채팅창에 입력:
```
/mcp
```
`stats-realty`, `stats`, `stats-finance` 등이 connected 로 나오면 완료입니다.

---

## 업데이트

코드나 API 키가 업데이트 되면 setup.bat 을 다시 실행하면 됩니다.  
저장소 pull + 패키지 재설치를 자동으로 처리합니다.

---

## 포함된 MCP

| MCP | 도메인 | 필요 키 |
|-----|--------|---------|
| stats-realty | 부동산 거래·가격지수 | 포함됨 |
| kb-price | KB 단지별 시세 | 없음 |
| stats | 인구·가구·생활인구 | 포함됨 |
| stats-finance | 금리·환율·기업공시 | 포함됨 |
| stats-job | 고용·임금·사업체 | 포함됨 |
| stats-biz | 상권·유동인구·임대 | 포함됨 |
| stats-transit | 지하철·버스·교통 | 포함됨 |
| stats-edu | 학교·학원·스쿨존 | 포함됨 |
| stats-env | 대기·환경·공원 | 포함됨 |
| stats-pubprice | 공동주택 공시가격 | VWORLD_API_KEY 별도 필요 |

---

## 문의

유진아빠 (심재민) — jaemyny@weolbu.com
