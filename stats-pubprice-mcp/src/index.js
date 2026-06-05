/**
 * stats-pubprice-mcp: 공동주택·단독주택·토지 공시가격 조회 MCP 서버
 *
 * 동작 흐름:
 *   1. 자연어 주소 → VWorld Search API → 법정동코드(pnu 10자리) 추출
 *   2. pnu + 파라미터 → VWorld NED 속성조회 API → 공시가격 JSON
 *   3. geometry 없음 (REST 속성 API 직접 반환) → 정제 후 리턴
 *
 * VWorld NED 엔드포인트:
 *   getApartHousingPriceAttr  : 공동주택(아파트) 공시가격
 *   getIndvdHousingPriceAttr  : 개별주택가격 (단독·다가구)
 *   getIndvdLandPriceAttr     : 개별공시지가 (토지)
 *
 * 환경변수:
 *   VWORLD_API_KEY  : VWorld 인증키 (필수)
 *   VWORLD_DOMAIN   : 키 발급 시 등록한 도메인 (기본: localhost)
 */

import { McpServer }           from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z }                    from "zod";

// ── 환경 변수 ────────────────────────────────────────────────────────────────
const VWORLD_KEY    = process.env.VWORLD_API_KEY ?? "";
const VWORLD_DOMAIN = process.env.VWORLD_DOMAIN  ?? "localhost";

const NED_BASE = "https://api.vworld.kr/ned/data";
const SEARCH_BASE = "https://api.vworld.kr/req/search";

if (!VWORLD_KEY) {
  process.stderr.write("[stats-pubprice-mcp] 경고: VWORLD_API_KEY가 설정되지 않았습니다.\n");
}

// ── MCP 서버 ─────────────────────────────────────────────────────────────────
const server = new McpServer({ name: "stats-pubprice-mcp", version: "1.0.0" });

// ─────────────────────────────────────────────────────────────────────────────
// 유틸: VWorld Search API → 법정동코드(pnu 10자리) 추출
//   우선순위: 지번 → 도로명 → POI
// ─────────────────────────────────────────────────────────────────────────────
async function geocodeToLdCode(address) {
  // 단지명 같은 고유명사는 POI 검색 결과로 오는 경우가 많음.
  // 아파트명을 제외한 '시/구/동' 위치 부분만 추출해 지번 주소 검색.
  const locationQuery = extractLocationOnly(address);

  // 검색 우선순위: 지번(정확) → 도로명 → 원본 지번 → 원본 도로명
  const candidates = [
    [locationQuery, "address", "parcel"],
    [locationQuery, "address", "road"],
    [address,       "address", "parcel"],
    [address,       "address", "road"],
    [address,       "place",   null],
  ];

  for (const [query, type, category] of candidates) {
    if (!query) continue;

    const u = new URL(SEARCH_BASE);
    u.searchParams.set("service",  "search");
    u.searchParams.set("request",  "search");
    u.searchParams.set("version",  "2.0");
    u.searchParams.set("crs",      "epsg:4326");
    u.searchParams.set("query",    query);
    u.searchParams.set("type",     type);
    u.searchParams.set("format",   "json");
    u.searchParams.set("key",      VWORLD_KEY);
    u.searchParams.set("domain",   VWORLD_DOMAIN);
    if (category) u.searchParams.set("category", category);

    const body = await fetch(u).then(r => r.json());
    if (body?.response?.status !== "OK") continue;

    const items = body.response.result?.items;
    if (!items?.length) continue;

    const first = items[0];
    const id = first.id ?? "";

    // VWorld 지번 ID: 19자리 숫자 = ldCode(10) + 산여부(1) + 본번(4) + 부번(4)
    if (/^\d{10,}$/.test(id)) {
      return {
        ldCode:   id.slice(0, 10),
        ldCodeNm: first.address?.parcel ?? first.address?.road ?? query,
        point:    first.point,
      };
    }

    // POI 결과인 경우: POI의 parcel 주소로 재시도
    if (id.startsWith("POI") && first.address?.parcel) {
      const u2 = new URL(SEARCH_BASE);
      u2.searchParams.set("service","search"); u2.searchParams.set("request","search");
      u2.searchParams.set("version","2.0");    u2.searchParams.set("crs","epsg:4326");
      u2.searchParams.set("query",  first.address.parcel);
      u2.searchParams.set("type","address"); u2.searchParams.set("category","parcel");
      u2.searchParams.set("format","json"); u2.searchParams.set("key", VWORLD_KEY);
      u2.searchParams.set("domain", VWORLD_DOMAIN);
      const body2 = await fetch(u2).then(r => r.json());
      const item2 = body2?.response?.result?.items?.[0];
      const id2 = item2?.id ?? "";
      if (/^\d{10,}$/.test(id2)) {
        return {
          ldCode:   id2.slice(0, 10),
          ldCodeNm: item2.address?.parcel ?? address,
          point:    item2.point ?? first.point,
        };
      }
    }
  }
  return null;
}

/**
 * 주소 문자열에서 아파트명·동호수·기타 비위치 정보를 제거하고
 * 시/구/동 수준의 위치 부분만 추출합니다.
 */
function extractLocationOnly(address) {
  return address
    // 동/호 정보 제거
    .replace(/\d{1,4}\s*동\s*\d{1,5}\s*호/g, "")
    .replace(/\d{1,5}\s*호/g, "")
    // 아파트 단지명 패턴 제거 (법정동 '동'과 충돌하지 않도록 단지명 패턴 먼저)
    .replace(/[가-힣A-Za-z0-9·\(\)]+(?:아파트|주공|마을|래미안|자이|힐스테이트|푸르지오|한양|현대|삼성|롯데|SK뷰|두산|대우|e편한|더샵|아이파크|파크|타워|시티|리버|그린|하늘|초록|쌍용|극동|부영|금호|우성|동아|코오롱|벽산|신동아|중흥|청구|진흥|성원|건영|한신|동신)/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// ─────────────────────────────────────────────────────────────────────────────
// 유틸: 공동주택공시가격 속성 조회
// ─────────────────────────────────────────────────────────────────────────────
async function fetchAptOfficialPrice({ pnu, stdrYear, dongNm, hoNm, aptName, pageNo = 1 }) {
  const u = new URL(`${NED_BASE}/getApartHousingPriceAttr`);
  u.searchParams.set("pnu",       pnu);
  u.searchParams.set("format",    "json");
  u.searchParams.set("numOfRows", "1000");
  u.searchParams.set("pageNo",    String(pageNo));
  u.searchParams.set("key",       VWORLD_KEY);
  u.searchParams.set("domain",    VWORLD_DOMAIN);

  if (stdrYear) u.searchParams.set("stdrYear", stdrYear);
  if (dongNm)   u.searchParams.set("dongNm",   dongNm);
  if (hoNm)     u.searchParams.set("hoNm",     hoNm);

  const body = await fetch(u).then(r => r.json());

  let items = body?.apartHousingPrices?.field ?? [];
  const total = parseInt(body?.apartHousingPrices?.totalCount ?? "0", 10);

  // 단지명 추가 필터 (API 미지원 → 클라이언트 필터링)
  if (aptName) {
    items = items.filter(f =>
      f.aphusNm?.includes(aptName) ||
      aptName.includes(f.aphusNm ?? "!!") // 부분 일치 양방향
    );
  }

  return { items, total };
}

// ─────────────────────────────────────────────────────────────────────────────
// 유틸: 주소에서 동번호·호번호·단지명 파싱
// ─────────────────────────────────────────────────────────────────────────────
function parseAddressParts(address) {
  const dongMatch = address.match(/(\d{1,4})\s*동/);
  const hoMatch   = address.match(/(\d{1,5})\s*호/);

  // 아파트 단지명 패턴
  const aptPattern = /([가-힣A-Za-z0-9·\(\)]+(?:아파트|주공|마을|래미안|자이|힐스테이트|푸르지오|한양|현대|삼성|롯데|SK뷰|두산|대우|e편한세상|더샵|아이파크|파크|타워|시티|리버|그린|하늘|초록|쌍용|극동|뉴코아|부영|금호|우성|동아|코오롱|벽산|신동아|중흥|청구|진흥|성원|건영|한신|동신|이편한|쌍문|장미|진달래))/;
  const aptMatch = address.match(aptPattern);

  return {
    dongNm:  dongMatch?.[1] ?? null,
    hoNm:    hoMatch?.[1] ?? null,
    aptName: aptMatch?.[1] ?? null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 유틸: 응답 데이터 정제
// ─────────────────────────────────────────────────────────────────────────────
function cleanResult(f) {
  return {
    기준연도:   f.stdrYear  ?? null,
    기준월:     f.stdrMt    ?? null,
    법정동코드: f.ldCode    ?? null,
    법정동:     f.ldCodeNm  ?? null,
    단지명:     f.aphusNm   ?? null,
    동명:       f.dongNm    ?? null,
    호명:       f.hoNm      ?? null,
    층:         f.floorNm   ?? null,
    전용면적_m2: f.prvuseAr  ?? null,
    공시가격_원: f.pblntfPc ? Number(f.pblntfPc) : null,
    pnu:        f.pnu       ?? null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// MCP Tool: get_apartment_official_price
// ─────────────────────────────────────────────────────────────────────────────
server.tool(
  "get_apartment_official_price",
  [
    "아파트 주소를 입력받아 공동주택 공시가격을 조회합니다.",
    "VWorld NED 속성조회 API(getApartHousingPriceAttr)를 사용합니다.",
    "동/호수를 포함하면 특정 세대, 생략하면 단지·동 전체 가격 목록을 반환합니다.",
  ].join(" "),
  {
    address: z.string().describe(
      "아파트 주소. 예: '경기도 부천시 중동 설악주공 303동 510호' / '부천시 중동 설악마을(주공)'"
    ),
    year: z.string().optional().describe(
      "공시 기준 연도 (YYYY). 미입력 시 모든 연도 반환. 예: '2025'"
    ),
    dong: z.string().optional().describe("동 번호. 예: '303'. address에 포함돼 있으면 생략 가능"),
    ho:   z.string().optional().describe("호 번호. 예: '510'. address에 포함돼 있으면 생략 가능"),
  },
  async ({ address, year, dong, ho }) => {
    const ERR_NO_ADDR = "해당 주소의 위치를 특정할 수 없거나 공시가격 데이터가 존재하지 않습니다.";

    if (!VWORLD_KEY) {
      return { content: [{ type: "text", text: "오류: VWORLD_API_KEY 환경변수가 설정되지 않았습니다." }] };
    }

    // ── 1단계: 주소 파싱 ──────────────────────────────────────────────────
    const { dongNm: parsedDong, hoNm: parsedHo, aptName } = parseAddressParts(address);
    const effectiveDong = dong ?? parsedDong;
    const effectiveHo   = ho   ?? parsedHo;

    // ── 2단계: 법정동코드 추출 ────────────────────────────────────────────
    let ldCode;
    try {
      const geo = await geocodeToLdCode(address);
      if (!geo?.ldCode) {
        return { content: [{ type: "text", text: ERR_NO_ADDR }] };
      }
      ldCode = geo.ldCode;
    } catch (e) {
      process.stderr.write(`[geocode 오류] ${e.message}\n`);
      return { content: [{ type: "text", text: ERR_NO_ADDR }] };
    }

    // ── 3단계: 공시가격 조회 ─────────────────────────────────────────────
    let items = [];
    try {
      const res = await fetchAptOfficialPrice({
        pnu:      ldCode,
        stdrYear: year ?? null,
        dongNm:   effectiveDong ?? null,
        hoNm:     effectiveHo   ?? null,
        aptName:  aptName       ?? null,
      });
      items = res.items;
    } catch (e) {
      process.stderr.write(`[API 오류] ${e.message}\n`);
      return { content: [{ type: "text", text: ERR_NO_ADDR }] };
    }

    if (!items.length) {
      return { content: [{ type: "text", text: ERR_NO_ADDR }] };
    }

    // ── 4단계: 정제 후 반환 ───────────────────────────────────────────────
    const results = items.map(cleanResult);

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          조회주소:   address,
          법정동코드: ldCode,
          조회연도:   year ?? "전체",
          동:         effectiveDong ?? "전체",
          호:         effectiveHo   ?? "전체",
          총건수:     results.length,
          공시가격목록: results,
        }, null, 2),
      }],
    };
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// MCP Tool: get_apartment_price_history (5년 이력 조회 편의 도구)
// ─────────────────────────────────────────────────────────────────────────────
server.tool(
  "get_apartment_price_history",
  "아파트 동·호수를 지정해 최근 N년간 공동주택 공시가격 변동 이력을 반환합니다.",
  {
    address: z.string().describe("아파트 주소. 예: '경기도 부천시 중동 설악마을(주공) 303동 510호'"),
    years:   z.number().optional().describe("조회 연수 (기본 5년). 예: 5"),
    dong:    z.string().optional().describe("동 번호. 예: '303'"),
    ho:      z.string().optional().describe("호 번호. 예: '510'"),
  },
  async ({ address, years = 5, dong, ho }) => {
    const ERR_NO_ADDR = "해당 주소의 위치를 특정할 수 없거나 공시가격 데이터가 존재하지 않습니다.";

    if (!VWORLD_KEY) {
      return { content: [{ type: "text", text: "오류: VWORLD_API_KEY 환경변수가 설정되지 않았습니다." }] };
    }

    const { dongNm: parsedDong, hoNm: parsedHo, aptName } = parseAddressParts(address);
    const effectiveDong = dong ?? parsedDong;
    const effectiveHo   = ho   ?? parsedHo;

    let ldCode;
    try {
      const geo = await geocodeToLdCode(address);
      if (!geo?.ldCode) return { content: [{ type: "text", text: ERR_NO_ADDR }] };
      ldCode = geo.ldCode;
    } catch {
      return { content: [{ type: "text", text: ERR_NO_ADDR }] };
    }

    const currentYear = new Date().getFullYear();
    const history = [];

    for (let y = currentYear; y >= currentYear - years + 1; y--) {
      try {
        const res = await fetchAptOfficialPrice({
          pnu:      ldCode,
          stdrYear: String(y),
          dongNm:   effectiveDong ?? null,
          hoNm:     effectiveHo   ?? null,
          aptName:  aptName       ?? null,
        });
        if (res.items.length) {
          // 같은 연도에 공시월(stdrMt)이 여럿일 수 있으므로 최신 월(최대값) 1건만 사용
          const latest = res.items.reduce((a, b) =>
            (a.stdrMt ?? "0") >= (b.stdrMt ?? "0") ? a : b
          );
          history.push({ ...cleanResult(latest), 전년대비_변동률: null });
        } else {
          history.push({ 기준연도: String(y), 공시가격_원: null, 메모: "데이터 없음" });
        }
      } catch {
        history.push({ 기준연도: String(y), 공시가격_원: null, 메모: "조회 오류" });
      }
    }

    // 연도 오름차순 정렬 + 변동률 계산
    history.sort((a, b) => Number(a.기준연도) - Number(b.기준연도));
    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1].공시가격_원;
      const curr = history[i].공시가격_원;
      if (prev && curr) {
        history[i].전년대비_변동률 = `${(((curr - prev) / prev) * 100).toFixed(1)}%`;
      }
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          조회주소:   address,
          법정동코드: ldCode,
          동:         effectiveDong ?? "전체",
          호:         effectiveHo   ?? "전체",
          조회기간:   `${currentYear - years + 1}~${currentYear}년`,
          공시가격이력: history,
        }, null, 2),
      }],
    };
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// 서버 실행
// ─────────────────────────────────────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
process.stderr.write("[stats-pubprice-mcp] 서버 시작 | NED getApartHousingPriceAttr\n");
