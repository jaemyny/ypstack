# kb-price-mcp 엔드포인트 명세

KB부동산 **비공식 내부 API**(`api.kbland.kr`) 5개 엔드포인트 명세 + 한글↔영문 키 매핑 + HAR 재캡처 워크플로.

> ⚠️ 이 API는 공개·계약된 것이 아니라 kbland.kr 웹의 내부 호출을 그대로 쓰는 것입니다.
> 예고 없이 경로·파라미터·응답 키가 바뀌거나 차단될 수 있습니다. 깨지면 아래 "HAR 재캡처"로 갱신하세요.

---

## 공통 규약

- **Base URL**: `https://api.kbland.kr`
- **메서드**: 전부 `GET`, 파라미터는 **한글 키** query string
- **필수 헤더** (없으면 차단됨): `Origin: https://kbland.kr`, `Referer: https://kbland.kr/`, 일반 브라우저 `User-Agent`
- **스로틀**: 요청 간 최소 `0.3s` 간격, 타임아웃 `15s`, 네트워크/5xx 시 1회 재시도 (`kb_client.py`)
- **응답 봉투**:
  ```json
  { "dataHeader": { "resultCode": "10000", "message": "..." },
    "dataBody":  { "data": <핵심 페이로드> } }
  ```
  - 성공 판정: `dataHeader.resultCode == "10000"`
  - `kb_client.get_json()` 은 성공 시 **`dataBody.data`** 만 반환, 실패 시 `{"error": ..., "path": ...}`

---

## 엔드포인트 5종

| # | path | 메서드 | 사용 도구 | 핵심 파라미터 |
|---|------|--------|-----------|----------------|
| 1 | `/land-complex/serch/intgraSerch` | GET | `kb_search_complex` | 검색설정명, 검색키워드, 출력갯수, 페이지설정값 |
| 2 | `/land-complex/complex/main` | GET | `kb_get_complex_basic` | 단지기본일련번호 |
| 3 | `/land-complex/complex/typInfo` | GET | `kb_get_complex_basic`, `kb_get_complex_price` | 단지기본일련번호 |
| 4 | `/land-price/price/BasePrcInfoNew` | GET | `kb_get_complex_price` | 단지기본일련번호, 면적일련번호 |
| 5 | `/land-price/price/WholQuotList` | GET | `kb_get_complex_price_history` | 단지기본일련번호, 면적일련번호, 기준년 |

> **호출 흐름**: ①검색 → `complex_no` 획득 → ③평형목록 → `area_no` 획득 → ④현재시세 / ⑤시계열.

---

### 1. 단지 통합검색 — `/land-complex/serch/intgraSerch`

- **파라미터**: `검색설정명=SRC_HSCM`(아파트), `검색키워드=<키워드>`, `출력갯수=<n>`, `페이지설정값=1`
- **응답 위치**: `data.data.HSCM.data[]` (총건수 `data.data.HSCM.totcnt`)

| 응답 키(한글/원문) | 매핑(영문) | 의미 |
|---|---|---|
| `COMPLEX_NO` | `complex_no` | 단지기본일련번호 (이후 모든 호출의 키) |
| `HSCM_NM` / `HSCM_NM_EXT` | `name` / `name_full` | 단지명 / 확장명 |
| `JUSO_ARNO` 또는 `BUBADDR` | `address_jibun` | 지번주소 |
| `NEWADDRESS` | `address_road` | 도로명주소 |
| `BUBCODE` | `law_dong_code` | 법정동코드 |
| `THS_NUM` | `total_households` | 총세대수 |
| `SQRMSR_SCOP` | `area_range_m2` | 면적 범위 |
| `MVIHS_DATE` | `build_ymd` | 입주(준공)년월 |
| `RPSNT_SQRMSR_NO` | `rep_area_no` | 대표면적일련번호 |
| `WGS84_LAT` / `WGS84_LNG` | `lat` / `lng` | 위경도 |
| `SLND_PERTY_NM` | `type` | 매물종별명 |

### 2. 단지 기본정보 — `/land-complex/complex/main`

- **파라미터**: `단지기본일련번호=<complex_no>`
- **응답 위치**: `data` (단일 객체)

| 응답 키(한글) | 매핑(영문) |
|---|---|
| `단지기본일련번호` | `complex_no` |
| `단지명` | `name` |
| `매물종별구분명` | `type` |
| `도로기본주소`/`신주소` | `address_road` |
| `구주소` | `address_jibun` |
| `법정동코드` | `law_dong_code` |
| `준공년월일` / `입주년수` | `build_ymd` / `build_age_years` |
| `총세대수` / `일반세대수` / `임대세대수` | `total_households` / `general_households` / `rental_households` |
| `총동수` / `최고층수` / `최저층수` | `total_buildings` / `max_floor` / `min_floor` |
| `총주차대수` / `세대당주차대수비율` | `total_parking` / `parking_per_household` |
| `난방방식구분명` / `난방연료구분명` | `heating` / `heating_fuel` |
| `시공사명` / `시행업체명` | `builder` / `developer` |
| `용적률내용` / `건폐율내용` | `floor_area_ratio` / `building_coverage_ratio` |
| `승강기유무` / `재건축여부` / `재개발여부` | `elevator` / `rebuilding_yn` / `redevelopment_yn` |
| `관리사무소전화번호내용` | `office_phone` |
| `wgs84위도` / `wgs84경도` | `lat` / `lng` |
| `viewCount` | `view_count` |
| `최소공급면적` / `최대공급면적` | `min_supply_area_m2` / `max_supply_area_m2` |
| `대표면적일련번호` / `대표공급면적` / `대표전용면적` | `rep_area_no` / `rep_supply_area_m2` / `rep_exclusive_area_m2` |

### 3. 평형(주택형) 목록 — `/land-complex/complex/typInfo`

- **파라미터**: `단지기본일련번호=<complex_no>`
- **응답 위치**: `data[]` (평형별 배열) — **`면적일련번호`(area_no)** 를 여기서 얻음

| 응답 키(한글) | 매핑(영문) |
|---|---|
| `면적일련번호` | `area_no` |
| `주택형타입내용` | `type_name` |
| `공급면적` / `공급면적평` | `supply_area_m2` / `supply_area_pyeong` |
| `전용면적` / `전용면적평` | `exclusive_area_m2` / `exclusive_area_pyeong` |
| `계약면적` / `계약면적평` | `contract_area_m2` / `contract_area_pyeong` |
| `세대수` / `방수` / `욕실수` | `households` / `rooms` / `bathrooms` |
| `전용률` | `exclusive_rate_pct` |
| `KMS평형코드` | `kms_size_code` |
| `매매건수` / `전세건수` / `월세건수` | `trade_count` / `jeonse_count` / `wolse_count` |

### 4. 현재 시세 — `/land-price/price/BasePrcInfoNew`

- **파라미터**: `단지기본일련번호`, `면적일련번호`
- **응답 위치**: `data.시세[]` (연결구분=일반/저층/탑층 등 별 1행) + `data` 레벨 매물 평균/건수
- **가격 단위: 만원**

| 응답 키(한글) | 매핑(영문) |
|---|---|
| `연결구분명` | `connection` (일반/저층/탑층 등) |
| `시세기준년월일` | `price_date` |
| `매매상한가`/`매매일반거래가`/`매매평균가`/`매매하한가`/`매매변동금액` | `trade_high`/`trade_general`/`trade_avg`/`trade_low`/`trade_change` `_만원` |
| `전세상한가`/`전세일반거래가`/`전세평균가`/`전세하한가`/`전세변동금액` | `jeonse_high`/`jeonse_general`/`jeonse_avg`/`jeonse_low`/`jeonse_change` `_만원` |
| `월세보증금액`/`월임대최저금액`/`월임대최고금액`/`월세금액` | `wolse_deposit`/`wolse_min`/`wolse_max`/`wolse_amount` `_만원` |
| `시세제공여부` / `시세미제공사유` | `is_provided` / `no_provide_reason` |
| (data 레벨) `매물매매평균가`/`매물전세평균가`/`매물월세보증금평균가`/`매물월세평균가` | `listing_trade_avg`/`listing_jeonse_avg`/`listing_wolse_deposit_avg`/`listing_wolse_avg` `_만원` |
| (data 레벨) `매매건수`/`전세건수`/`월세건수` | `trade_count`/`jeonse_count`/`wolse_count` |

### 5. 시세 시계열(월별) — `/land-price/price/WholQuotList`

- **파라미터**: `단지기본일련번호`, `면적일련번호`, `기준년=<YYYY>`
- **응답 위치**: `data.시세[].items[]` (월별)
- **주의**: 1회 호출 = `기준년` 1년치. 여러 해가 필요하면 연도를 바꿔 반복 호출 후 `기준년월` 기준 병합/중복제거 (`kb_get_complex_price_history` 가 처리).

| 응답 키(한글) | 매핑(영문) |
|---|---|
| `기준년월` | `year_month` |
| `매매상한가`/`매매일반거래가`/`매매하한가` | `trade_high`/`trade_general`/`trade_low` `_만원` |
| `전세상한가`/`전세일반거래가`/`전세하한가` | `jeonse_high`/`jeonse_general`/`jeonse_low` `_만원` |
| `월세보증금액`/`월임대최저금액`/`월임대최고금액` | `wolse_deposit`/`wolse_min`/`wolse_max` `_만원` |

---

## HAR 재캡처 워크플로 (스키마가 깨졌을 때)

KB가 경로/키를 바꾸면 도구가 조용히 빈 값을 반환할 수 있습니다. 다음 순서로 갱신하세요.

1. **Chrome 으로 `https://kbland.kr` 접속** → 대상 단지 검색 → 단지 상세 → **시세 탭**까지 클릭.
2. **DevTools(F12) → Network 탭** → 상단 필터에 `api.kbland.kr` 입력, **Fetch/XHR** 만 표시.
3. 검색·시세 조회 동작을 실제로 수행하며 발생하는 요청을 찾는다 (이 문서의 path와 대조).
4. 해당 요청 클릭 →
   - **Headers → Request URL / Query String Parameters**: path 와 **한글 파라미터**를 이 문서·`server.py` 와 대조.
   - **Response**: `dataBody.data` 하위 JSON 구조와 키 이름을 확인 → 바뀐 키를 영문 매핑에 반영.
5. (선택) 요청 우클릭 → **Copy → Copy as HAR** 로 저장해 두면 재현·공유에 유용.
6. **반영**: `server.py` 의 해당 도구에서 `get_json(path, {한글파라미터})` 와 응답 키 `.get("한글키")` 를 수정하고, **이 문서를 함께 갱신**한다.

### 차단/이상 징후 판별
- `RemoteDisconnected` / 타임아웃 반복 → IP·UA 차단 의심 (헤더의 Origin/Referer 확인).
- `resultCode != "10000"` → `dataHeader.message` 확인 (파라미터 오류·권한 등).
- HTTP 200 인데 `dataBody.data` 가 비거나 키가 사라짐 → **스키마 변경** → 위 절차로 재캡처.

> 회귀를 조기에 잡으려면 잠실엘스·은마 등 고정 단지로 4개 도구를 주기적으로 호출하는 smoke 테스트(PRD §5.1.2) 권장.

---

## 6. 주변 학교 (학군) — `/land-complex/map/scholMarkerList`

- **사용 도구**: `kb_get_complex_schools`
- **인증 불필요**: 웹은 `authorization: bearer <토큰>` 를 붙이지만 API는 요구하지 않음 (토큰 없이 200·정상 데이터 확인, 2026-06).
- **파라미터** (지도 bounding box):

| 파라미터 | 의미 |
|---|---|
| `scholCode` | 학교급 콤마 구분: `03`=초등 / `04`=중학교 / `05`=고등 (예: `03,04,05`) |
| `startLat` / `startLng` | bbox 남서(좌하단) 위도/경도 |
| `endLat` / `endLng` | bbox 북동(우상단) 위도/경도 |
| `zoomLevel` | 지도 줌 레벨 (16 사용) |

- **응답**: `data[]` — `학교식별자`→`school_id`, `학교명`→`name`, `학교과정분류구분`→`level`(03/04/05), `wgs84위도/경도`→`lat/lng`.

> 도구는 `complex/main` 의 `wgs84위경도` 를 중심으로 `radius_m` 반경 bbox 를 만들어 호출하고, 단지~학교 거리(m, haversine)를 계산해 거리순 정렬한다.

## 7. 주변 편의시설 — `/land-complex/honeyLocation/{academy,hospital,subway,starbucks}MarkerList`

- **사용 도구**: `kb_get_complex_facilities`
- **인증 불필요**. **파라미터**: §6 과 동일한 bbox(`startLat/startLng/endLat/endLng` + `zoomLevel`). 종류별 코드 파라미터 없이 전체 반환.
- **응답**: `data[]` (종류별 키 상이)

| 종류 | 엔드포인트 | 주요 응답 키 |
|---|---|---|
| 학원 | `honeyLocation/academyMarkerList` | `학원목록`(`\|` 구분), `학원개수`, `대표종류`, `wgs84위/경도` |
| 병원 | `honeyLocation/hospitalMarkerList` | `병원목록`(`\|` 구분), `병원개수`, `대표종류`, `wgs84위/경도` |
| 지하철 | `honeyLocation/subwayMarkerList` | `지하철역명`, `지하철호선명`, `wgs84위/경도` |
| 스타벅스 | `honeyLocation/starbucksMarkerList` | `지점명`, `wgs84위/경도` |

## 8. API 없음 / 불필요로 판단한 후보 (2026-06)

| 후보 | 판단 |
|---|---|
| **보유세 시뮬** | KB 직접 API 없음 (공시지가 `complex/pubLandPriceByDong` 만 존재). 공시가 기반 계산은 별도 과제 → 미구현 |
| **매물수 추이** | 현재 건수는 `complexResteBrhs/propCountByTradeKind`(param `단지기본일련번호`)로 가능하나 **시계열 없음**, 현재 건수는 이미 `complex/main`·`kb_get_complex_price` 에 노출 → 별도 도구 불필요 |

> **발굴 방법 메모**: `https://kbland.kr/` JS 번들에서 `land-*` 경로를 추출해 후보를 좁히고, 실제 **요청 파라미터(bbox 등)** 는 브라우저 DevTools Network 의 실제 요청에서 확보했다. bearer 토큰은 웹이 붙이지만 API는 요구하지 않는다.
