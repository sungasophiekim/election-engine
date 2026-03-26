"use client";
import { useState } from "react";

// ════════════════════════════════════════════════════════════════════
// RESEARCH PAGE — 여론에 미치는 영향 분석 + 학술 연구 기반
// ════════════════════════════════════════════════════════════════════

// 금주 현황 — 매주 리포트 생성 시 업데이트 (2026-03-21 기준)
const WEEKLY_UPDATE = "2026-03-21";

const FACTORS = [
  {
    id: "central",
    icon: "🏛",
    title: "중앙정치 환경",
    subtitle: "대통령·정당 프리미엄",
    impact: 5,
    impactLabel: "매우 큼",
    brief: "이재명 67% → 대통령 효과 강세. 민주 39% vs 국힘 27% (+12%p). 우리에게 유리한 환경.",
    direction: "favorable" as const,
    description: "지방선거 판세의 약 50%는 중앙정치가 결정한다. 새 정부 임기 초반의 '대통령 효과'가 여당 후보를 견인하며, 대통령 지지율과 지방선거 득표율의 상관계수는 0.7~0.9 수준.",
    evidence: [
      "7대 지선(2018): 문재인 지지율 78% → 김경수 52.8% 당선",
      "8대 지선(2022): 윤석열 지지율 52%(초기) → 박완수 65.7% 당선",
      "경남은 시도지사 선거에서 세종(-24.15%) 다음으로 민주당 득표율 하락폭 최대(-23.38%)",
    ],
    mechanism: "대통령 지지율 ↑ → 여당 정당 지지율 ↑ → 여당 후보 지지율 ↑ (대통령효과/역풍 연동)",
    ourEngine: "national_poll_collector → Leading Index 대통령효과(8%)",
    weeklyDetail: "이재명 대통령 직무 긍정 67%(갤럽 3월 3주). 민주당 39% vs 국힘 27%로 정당 격차 +12%p. 대통령 효과 지속 중이나 취임 3개월차 진입으로 하락 추세 모니터링 필요. 대통령효과 점수 +16.3 → Leading Index에 양(+) 반영.",
    sources: [
      { title: "제9대 경남도지사 선거 승리 전략 보고서", url: "", type: "캠프 내부" },
      { title: "한국갤럽 — 대통령 직무수행 평가", url: "https://www.gallup.co.kr/gallupdb/reportContent.asp?seqNo=1559", type: "조사기관" },
    ],
  },
  {
    id: "event",
    icon: "🎯",
    title: "후보 이벤트",
    subtitle: "정책발표·방문·토론·스캔들",
    impact: 5,
    impactLabel: "매우 큼",
    brief: "사법리스크 7건 모니터링 중. 민생지원금 선점 실패 후 대응 공약 필요.",
    direction: "warning" as const,
    description: "후보의 직접적 행동이 여론조사에 가장 빠르게 반영된다. 정책 발표(+1.5%p), TV 토론(±2.0%p), 스캔들(-2.5%p)로 단기간 큰 변동을 만든다.",
    evidence: [
      "박완수 단수공천 확정 → 네이버 검색 278% 급등, 여론조사 관심도 상승",
      "김경수 '도민 10만원' 공약 발표 → 맘카페 반응 급등",
      "사법리스크 프레임 확산 → 지지율 하락 리스크 (현재 7건 모니터링 중)",
    ],
    mechanism: "후보 행동 → 미디어 보도 → 유권자 인지 → 여론 변화 (통상 1~7일 lag)",
    ourEngine: "event_impact(8유형) + Pre-Trigger + Attribution",
    weeklyDetail: "사법리스크 프레임이 지속적 부담(-2~3%p 추정). 상대 민생지원금 발표 선점 실패. 금주 우리 측 주요 이벤트: 경남 AI 대전환 공약 발표(예상 +1.5%p). TV 토론 일정 미확정이나 토론 시 예상 영향 ±2.0%p로 준비 필요.",
    sources: [
      { title: "제20대 총선 유권자 투표행태 영향 요인 연구", url: "https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002212933", type: "학술논문" },
      { title: "경남대전환 Trend Report 01 (260320)", url: "", type: "캠프 내부" },
    ],
  },
  {
    id: "media",
    icon: "📺",
    title: "미디어 프레이밍",
    subtitle: "뉴스 톤·분량·Horse Race",
    impact: 4,
    impactLabel: "큼",
    brief: "뉴스 노출 열세 (652 vs 796건). 지역 언론은 상대적 중립. 프레임 전환 필요.",
    direction: "warning" as const,
    description: "미디어가 후보를 어떤 프레임으로 다루는가가 유권자 인식을 결정한다. '승자편승 효과'(앞선 후보에 투표 경향)와 '프레임 전쟁'(변화 vs 안정)이 핵심.",
    evidence: [
      "김경수 프레임: '변화 리더십' | '경제 공약' | '지역 주도' (AI 감성 분석)",
      "박완수 프레임: '안정 행정' | '경험' | '안전' (AI 감성 분석)",
      "빅카인즈 652건 vs 796건 — 박완수 뉴스 노출량이 22% 많음",
    ],
    mechanism: "미디어 노출량 ↑ → 인지도 ↑ → 지지율 ↑ (단, 부정 보도는 역효과)\nHorse Race 보도 → 앞선 후보 편승 효과 → 격차 확대",
    ourEngine: "AI 감성(Claude) + regional_media_collector(8개 지역 언론)",
    weeklyDetail: "전국 언론: 박완수 노출 우위 22%. 김경수 핵심 연관어가 '이재명/정청래'에 묶여 중앙정치 프레임 지배적. 지역 언론(KNN/경남신문): 상대적 중립, 도정 이슈 중심 보도. 지역 언론에서 '변화/경남 주도' 프레임 확산 전략 필요.",
    sources: [
      { title: "대중매체의 후보이미지 형성 및 유권자 투표행위 연구", url: "https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART001250499", type: "학술논문" },
      { title: "Six ways the media influences elections (U of Oregon)", url: "https://journalism.uoregon.edu/news/six-ways-media-influences-elections", type: "해외연구" },
      { title: "Stanford — How Polls Influence Behavior", url: "https://www.gsb.stanford.edu/insights/how-polls-influence-behavior", type: "해외연구" },
    ],
  },
  {
    id: "economy",
    icon: "💰",
    title: "경제 체감",
    subtitle: "물가·일자리·부동산",
    impact: 4,
    impactLabel: "큼",
    brief: "고용률 61.8%, 물가 2.0%. 조선업 호황이나 제조업 소폭 회복. 현직에 약간 유리.",
    direction: "neutral" as const,
    description: "유권자가 체감하는 경제 상황이 현직에 대한 평가를 결정한다. 경남은 조선업 경기, 물가, 부동산 시세가 직접적 변수.",
    evidence: [
      "한국인 투표행태 최우선 영향 요인 = 경제 이슈 (KCI 연구)",
      "경남 조선업 호황 → 거제/창원 고용 개선 → 현직(박완수) 유리 요소",
      "물가 상승 체감 → 현직 불만 → 도전자(김경수) 유리 요소",
    ],
    mechanism: "경제 체감 악화 → 현직 책임론 → 도전자 유리\n경제 체감 개선 → 현직 성과론 → 현직 유리",
    ourEngine: "economic_collector(6개 지표) → Leading Index economy(5%)",
    weeklyDetail: "2월 기준: 고용률 61.8%(전월 대비 +0.3%p), 실업률 2.9%, 물가 2.0%. 제조업 생산지수 +0.3%로 소폭 회복. 조선업 호황 지속(방산 수출 증가). 부동산 -0.2%로 약세. 경제 체감 점수 -0.9(보합) → 현직에 미세 유리. 도전자 입장에서 물가 이슈 공략 여지.",
    sources: [
      { title: "Factors Influencing Voting Decision (MDPI Social Sciences)", url: "https://www.mdpi.com/2076-0760/12/9/469", type: "해외연구" },
      { title: "지역유권자의 투표행태와 후보자의 결정요인 (2022 지방선거)", url: "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002934928", type: "학술논문" },
    ],
  },
  {
    id: "org",
    icon: "🏗",
    title: "조직 동원",
    subtitle: "노조·종교·맘카페·향우회",
    impact: 3,
    impactLabel: "보통~큼",
    brief: "민주노총 간담회 진행. 맘카페 반응 활발. 공식 지지선언 릴레이 준비 중.",
    direction: "favorable" as const,
    description: "조직적 지지선언과 투표 동원이 실제 투표율과 득표율에 직접 영향. 경남에서 민주노총(5만), 맘카페(25만)의 영향력이 특히 큼.",
    evidence: [
      "7대 지선: 창원 성산구 노동계 밀집지에서 김경수 62% (최고 득표)",
      "창원줌마렐라(25만) = 경남 최대 여론 형성 채널 (캠프 보고서)",
      "민주노총 경남본부 간담회 → 영향력 점수 48 (조직 시그널)",
    ],
    mechanism: "조직 지지선언 → 미디어 보도 + 내부 동원\n맘카페 여론 형성 → 신도시 3040 투표율 상승\n노조 동원 → 산업단지 투표율 상승",
    ourEngine: "org_signal_detector(25개) + 맘카페 5곳 + community 22곳",
    weeklyDetail: "민주노총 경남본부 간담회 완료(영향력 48). 창원줌마렐라에서 '도민 10만원' 관련 게시글 반응 활발. 공식 지지선언 릴레이는 D-60 이후 시작 예정. 현재 비공식 접촉 단계. 맘카페 활성도 보통(0.4/1.0).",
    sources: [
      { title: "경남 맘카페 초밀착 공략 방안 (캠프 전략 보고서)", url: "", type: "캠프 내부" },
      { title: "제9대 경남도지사 선거 승리 전략 보고서", url: "", type: "캠프 내부" },
    ],
  },
  {
    id: "opponent",
    icon: "⚔",
    title: "상대 캠프 행동",
    subtitle: "정책선점·네거티브·실수",
    impact: 4,
    impactLabel: "큼",
    brief: "박완수 단수공천 확정. 민생지원금 선점. 사법리스크 프레임 공격 지속.",
    direction: "unfavorable" as const,
    description: "상대 캠프의 정책 선점, 네거티브 공격, 실수가 여론을 급변시킬 수 있다. '민생지원금 사건'처럼 사전 감지 실패 시 선점 기회를 잃음.",
    evidence: [
      "민생지원금 사건: 도청 보도자료 + 기자 엠바고 → 감지 실패 → 선점 불가",
      "박완수 단수공천 → 검색량 278% 급등 → 일시적 관심 집중",
      "사법리스크 프레임 공격 → 현재 7건 모니터링 중",
    ],
    mechanism: "상대 정책 발표 → 미디어 주목 → 우리 공약 무력화\n네거티브 공격 → 반복 노출 → 신뢰 하락",
    ourEngine: "Pre-Trigger(4채널) + event_impact(상대 이벤트 정량화)",
    weeklyDetail: "박완수 국힘 단수공천 확정 → 경쟁 구도 고착. 민생지원금 도청 발표 선점(감지 실패). 사법리스크 프레임 7건 지속 모니터링. 상대 검색량 278% 급등 후 안정세. 금주 상대 행보: 동부권 현장 방문 집중(예상 +0.3%p/지역).",
    sources: [
      { title: "Persuasion and dissuasion in political campaigns (Springer)", url: "https://link.springer.com/article/10.1007/s11129-025-09300-y", type: "해외연구" },
    ],
  },
  {
    id: "turnout",
    icon: "🗳",
    title: "투표율 변수",
    subtitle: "세대별·지역별 참여율",
    impact: 5,
    impactLabel: "매우 큼 (당락 결정)",
    brief: "여론조사 38:38이지만 투표율 반영 시 43:57. 구조적 열세 약 14%p (7대 실제 투표율 기반).",
    direction: "unfavorable" as const,
    description: "같은 지지율이라도 투표율에 따라 결과가 뒤집힌다. 7대(2018) 경남 투표율 65.8% 기준, 2030 투표율이 이미 52~54%로 높았으나 60+의 72~75%가 구조적 열세를 만든다.",
    evidence: [
      "7대(2018) 경남 투표율 65.8% (남 65.6%, 여 68.2%) — 중앙선관위",
      "7대 연령별 투표율: 20대 52%, 30대 54.3%, 40대 58.6%, 50대 63.3%, 60대 72.5%, 70대 74.5%, 80+ 50.8%",
      "경남 연령 구조 변화: 2030세대 50.5%→37.7%(-12.8%p), 60+ 27.5%→39.5%(+12%p)",
      "→ 인구 구조만으로 약 13~14만표를 잃고 시작 (승리 전략 보고서)",
    ],
    mechanism: "전체 투표율 ↑ → 무당층 참여 ↑ → 변화 요구 ↑ → 도전자 유리\n청년 투표율 ↑ → 민주당 유리\n농촌 고령 투표율 ↑ → 국힘 유리",
    ourEngine: "turnout_predictor(세대별 × 투표율 × 지지율, 5 시나리오) — 7대 실제 투표율 기저",
    weeklyDetail: "7대 실제 투표율 반영 후: 현재 추세 시나리오 김경수 42.9% vs 박완수 57.1% (격차 -14.2%p). 이전 8대 추정 대비 +2.4%p 개선. 3040 집중 동원 시 43.2% vs 56.8%(-13.6%p). 승리 공식: 3040 투표율 극대화 + 50대 지지율 45→50% + 60대 격차 축소.",
    sources: [
      { title: "지방선거 투표율의 결정요인 연구", url: "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001519807", type: "학술논문" },
      { title: "선거별 투표율 결정 요인 — 서울시 집합자료 분석 (1987~2010)", url: "https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE02380495", type: "학술논문" },
      { title: "제9대 경남도지사 선거 승리 전략 보고서", url: "", type: "캠프 내부" },
    ],
  },
];

export function ResearchPage() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tab, setTab] = useState("factors");

  return (
    <div className="space-y-3 max-w-5xl mx-auto">
      {/* Tab Header */}
      <div className="wr-card border-t-2 border-t-cyan-600">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[14px] font-bold text-cyan-300">🔬 선거 전략 리서치</h2>
            <div className="flex rounded border border-[#1a2844] overflow-hidden">
              <button onClick={() => setTab("factors")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "factors" ? "bg-cyan-600/30 text-cyan-400" : "text-gray-600 hover:text-gray-400"
                }`}>여론 영향 요인</button>
              <button onClick={() => setTab("turnout")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "turnout" ? "bg-amber-600/30 text-amber-400" : "text-gray-600 hover:text-gray-400"
                }`}>투표율 예측 모델</button>
              <button onClick={() => setTab("event")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "event" ? "bg-emerald-600/30 text-emerald-400" : "text-gray-600 hover:text-gray-400"
                }`}>이벤트 임팩트</button>
              <button onClick={() => setTab("regional")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "regional" ? "bg-purple-600/30 text-purple-400" : "text-gray-600 hover:text-gray-400"
                }`}>지역 언론</button>
            </div>
          </div>
          {tab === "factors" && (
          <>
            <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
              학술 연구 + 캠프 내부 전략 보고서 + 해외 연구를 종합하여, 경남도지사 선거 여론조사에
              영향을 미치는 핵심 요인들을 정리하고 우리 엔진의 커버리지를 분석합니다.
            </p>
            <div className="flex items-center gap-3 mt-2">
              <span className="text-[8px] text-blue-400">📄 학술논문 4건</span>
              <span className="text-[8px] text-emerald-400">🌐 해외연구 4건</span>
              <span className="text-[8px] text-amber-400">📋 캠프내부 4건</span>
              <button
                onClick={() => window.open("/api/v2/research-report", "_blank")}
                className="ml-auto text-[9px] bg-cyan-950/40 border border-cyan-700/40 text-cyan-300 px-3 py-1 rounded hover:bg-cyan-900/50 font-bold transition"
              >
                📄 PDF 내보내기
              </button>
            </div>
          </>
          )}
        </div>
      </div>

      {tab === "factors" ? (
      <>

      {/* Overview Matrix */}
      <div className="wr-card">
        <div className="wr-card-header">영향 요인 × 엔진 커버리지</div>
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-gray-600 border-b border-[#1a2844]">
                <th className="text-left py-2 px-3">요인</th>
                <th className="text-center py-2 px-2">영향</th>
                <th className="text-center py-2 px-2">방향</th>
                <th className="text-left py-2 px-3">금주 현황</th>
              </tr>
            </thead>
            <tbody>
              {FACTORS.map((f) => {
                const dirColor = f.direction === "favorable" ? "text-emerald-400" :
                  f.direction === "unfavorable" ? "text-red-400" :
                  f.direction === "warning" ? "text-amber-400" : "text-gray-400";
                const dirIcon = f.direction === "favorable" ? "▲" :
                  f.direction === "unfavorable" ? "▼" :
                  f.direction === "warning" ? "⚠" : "—";
                return (
                  <tr key={f.id}
                    onClick={() => setExpanded(expanded === f.id ? null : f.id)}
                    className="border-b border-[#0e1825] cursor-pointer hover:bg-white/[0.02] transition">
                    <td className="py-2 px-3">
                      <span className="text-base mr-1.5">{f.icon}</span>
                      <span className="text-gray-200 font-bold">{f.title}</span>
                    </td>
                    <td className="text-center py-2 px-2">
                      <div className="flex justify-center gap-0.5">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < f.impact ? "bg-amber-400" : "bg-gray-800"}`} />
                        ))}
                      </div>
                    </td>
                    <td className="text-center py-2 px-2">
                      <span className={`text-[11px] font-bold ${dirColor}`}>{dirIcon}</span>
                    </td>
                    <td className="py-2 px-3 text-gray-400 text-[9px]">{f.brief}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed Cards */}
      {FACTORS.map((f) => (
        <div key={f.id} className={`wr-card transition-all ${expanded === f.id ? "border-l-2 border-l-cyan-500" : ""}`}>
          <div
            className="wr-card-header flex items-center justify-between cursor-pointer"
            onClick={() => setExpanded(expanded === f.id ? null : f.id)}
          >
            <div className="flex items-center gap-2">
              <span className="text-lg">{f.icon}</span>
              <span className="text-cyan-300">{f.title}</span>
              <span className="text-[8px] text-gray-600 normal-case tracking-normal font-normal">{f.subtitle}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < f.impact ? "bg-amber-400" : "bg-gray-800"}`} />
                ))}
              </div>
              <span className="text-[10px] text-gray-600">{expanded === f.id ? "▼" : "▶"}</span>
            </div>
          </div>

          {expanded === f.id && (
            <div className="px-4 py-3 space-y-3">
              {/* 설명 */}
              <div className="text-[11px] text-gray-300 leading-relaxed">{f.description}</div>

              {/* 근거 */}
              <div className="bg-[#080d16] rounded-lg p-3">
                <div className="text-[9px] text-amber-400 font-bold uppercase tracking-widest mb-1.5">경남 적용 근거</div>
                {f.evidence.map((e, i) => (
                  <div key={i} className="text-[10px] text-gray-400 py-0.5 flex gap-2">
                    <span className="text-amber-400/60 shrink-0">▸</span>
                    <span>{e}</span>
                  </div>
                ))}
              </div>

              {/* 메커니즘 */}
              <div className="bg-[#080d16] rounded-lg p-3">
                <div className="text-[9px] text-blue-400 font-bold uppercase tracking-widest mb-1.5">영향 메커니즘</div>
                <div className="text-[10px] text-blue-300/80 whitespace-pre-line leading-relaxed">{f.mechanism}</div>
              </div>

              {/* 엔진 현황 + GAP */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-cyan-950/10 border border-cyan-800/20 rounded-lg p-3 col-span-2">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-[9px] text-cyan-400 font-bold uppercase tracking-widest">📋 금주 현황 ({WEEKLY_UPDATE})</div>
                    <div className="text-[8px] text-gray-600">{f.ourEngine}</div>
                  </div>
                  <div className="text-[10px] text-gray-300 leading-relaxed">{f.weeklyDetail}</div>
                </div>
              </div>

              {/* 출처 */}
              <div className="border-t border-[#1a2844] pt-2">
                <div className="text-[8px] text-gray-600 uppercase tracking-widest mb-1">연구 출처</div>
                <div className="space-y-0.5">
                  {f.sources.map((s, i) => (
                    <div key={i} className="flex items-center gap-2 text-[9px]">
                      <span className={`px-1.5 py-0.5 rounded text-[7px] ${
                        s.type === "학술논문" ? "bg-blue-950/40 text-blue-400" :
                        s.type === "해외연구" ? "bg-emerald-950/40 text-emerald-400" :
                        "bg-amber-950/40 text-amber-400"
                      }`}>{s.type}</span>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noopener noreferrer"
                          className="text-gray-400 hover:text-cyan-400 transition underline underline-offset-2">
                          {s.title}
                        </a>
                      ) : (
                        <span className="text-gray-500">{s.title}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      ))}

      {/* 종합 분석 */}
      <div className="wr-card border-t-2 border-t-amber-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[12px] font-bold text-amber-300">📊 종합 판세 — {WEEKLY_UPDATE} 기준</h3>

          <div className="grid grid-cols-4 gap-2">
            <div className="bg-emerald-950/10 border border-emerald-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">유리</div>
              <div className="text-lg font-black text-emerald-400">2</div>
              <div className="text-[8px] text-emerald-400/60">중앙정치, 조직</div>
            </div>
            <div className="bg-amber-950/10 border border-amber-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">주의</div>
              <div className="text-lg font-black text-amber-400">2</div>
              <div className="text-[8px] text-amber-400/60">이벤트, 미디어</div>
            </div>
            <div className="bg-gray-800/30 border border-gray-700/30 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">중립</div>
              <div className="text-lg font-black text-gray-400">1</div>
              <div className="text-[8px] text-gray-500">경제</div>
            </div>
            <div className="bg-red-950/10 border border-red-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">불리</div>
              <div className="text-lg font-black text-red-400">2</div>
              <div className="text-[8px] text-red-400/60">상대행동, 투표율</div>
            </div>
          </div>

          <div className="bg-[#080d16] rounded-lg p-3">
            <div className="text-[10px] text-amber-300 font-bold mb-1.5">🎯 금주 핵심 판단</div>
            <div className="text-[10px] text-gray-300 leading-relaxed">
              대통령 효과(67%)와 정당 우위(+12%p)가 최대 자산이나, 투표율 구조(42:58)와 사법리스크 프레임이 상쇄.
              여론조사 38:38 초박빙은 실제 투표 시 약 15만표 열세를 의미.
              <span className="text-cyan-400 font-bold"> 승부처: 50대 지지율 확보 + 3040 투표율 극대화 + 지역 프레임 전환.</span>
            </div>
          </div>

          <div className="text-[8px] text-gray-600 border-t border-[#1a2844] pt-2 flex justify-between">
            <span>학술논문 4건, 해외연구 4건, 캠프 전략보고서 4건 종합. AI 기반 분석이며 참고용.</span>
            <span className="text-gray-700">매주 리포트 생성 시 자동 업데이트</span>
          </div>
        </div>
      </div>
      </>
      ) : tab === "turnout" ? (
      <TurnoutResearch />
      ) : tab === "event" ? (
      <EventImpactResearch />
      ) : (
      <RegionalMediaResearch />
      )}
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// TAB 2: 투표율 예측 모델 리서치
// ════════════════════════════════════════════════════════════════════

function TurnoutResearch() {
  return (
    <>
      {/* 모델 개요 */}
      <div className="wr-card border-t-2 border-t-amber-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[13px] font-bold text-amber-300">🗳 투표율 예측 모델 — 근거와 구조</h3>
          <p className="text-[10px] text-gray-400 leading-relaxed">
            세대별 인구 × 투표율 × 지지율을 교차하여 실제 투표 결과를 추정합니다.
            투표율은 7대 지선(2018) 중앙선관위 실제 데이터 (경남 65.8%).
            지지율은 NESDC 양자대결 3개 조사 raw data 평균. 무응답은 50:50 균등 배분.
            현재 추세: <span className="text-emerald-400 font-bold">김경수 51.2% vs 박완수 48.8%</span> (초박빙).
          </p>

          {/* 핵심 공식 */}
          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844] space-y-1">
            <div className="text-[10px] text-cyan-400 font-mono text-center">
              후보별 예상 득표 = Σ(세대별) [ 유권자 수 × 투표율 × 유효 지지율 ]
            </div>
            <div className="text-[9px] text-gray-500 font-mono text-center">
              유효 지지율 = (raw 지지 + 무응답투표 × 0.5) / (김raw + 박raw + 무응답투표)
            </div>
            <div className="text-[8px] text-gray-600 text-center">
              무응답자 중 50% 투표 참여, 투표하는 무응답자는 김:박 50:50 균등 배분
            </div>
          </div>
        </div>
      </div>

      {/* 변수 1: 세대별 인구 */}
      <div className="wr-card">
        <div className="wr-card-header text-amber-400">변수 ① 세대별 유권자 수</div>
        <div className="px-4 py-3 space-y-2">
          <div className="text-[9px] text-gray-500">출처: 제9대 경남도지사 선거 승리 전략 보고서 표10 (2025 대선 경남 선거인수)</div>
          <table className="w-full text-[10px]">
            <thead><tr className="text-gray-600 border-b border-[#1a2844]">
              <th className="text-left py-1.5 px-2">세대</th>
              <th className="text-right py-1.5 px-2">비중</th>
              <th className="text-right py-1.5 px-2">유권자(만)</th>
              <th className="text-right py-1.5 px-2">7년 변화</th>
              <th className="text-left py-1.5 px-2">의미</th>
            </tr></thead>
            <tbody>
              {[
                ["20대", "10.0%", "26.3", "-4.5%p", "전 연령 최대 하락"],
                ["30대", "11.6%", "30.5", "-4.2%p", "신도시 주축 감소"],
                ["40대", "16.2%", "42.6", "-4.0%p", "핵심 허리층 축소"],
                ["50대", "20.9%", "55.0", "+0.1%p", "보합 (최대 유권자)"],
                ["60대", "20.9%", "55.0", "+6.1%p", "베이비부머 유입 급증"],
                ["70대+", "18.5%", "48.7", "+5.8%p", "초고령화 가속"],
              ].map(([age, pct, voters, change, note], i) => (
                <tr key={i} className="border-b border-[#0e1825]">
                  <td className="py-1.5 px-2 text-gray-200 font-bold">{age}</td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{pct}</td>
                  <td className="py-1.5 px-2 text-right text-white font-mono">{voters}</td>
                  <td className={`py-1.5 px-2 text-right font-mono ${(change as string).startsWith("-") ? "text-red-400" : "text-emerald-400"}`}>{change}</td>
                  <td className="py-1.5 px-2 text-gray-500">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="bg-red-950/10 border border-red-800/20 rounded-lg p-2.5 text-[10px] text-red-300/80">
            ⚠ 핵심: 2030세대 50.5%→37.7%(-12.8%p 급감), 60+ 27.5%→39.5%(+11.9%p 폭증)<br/>
            → "인구 구조만으로 약 13~14만표를 잃고 시작" (승리 전략 보고서)
          </div>
        </div>
      </div>

      {/* 변수 2: 투표율 */}
      <div className="wr-card">
        <div className="wr-card-header text-amber-400">변수 ② 세대별 투표율 — 7대 지선(2018) 실제</div>
        <div className="px-4 py-3 space-y-2">
          <div className="text-[9px] text-gray-500">
            출처: 중앙선관위 제7회 지방선거 투표율 분석 보고서 (경남 전체 65.8%)<br/>
            보정 없이 7대 실제 투표율을 그대로 사용. 시나리오에서 투표율 변동만 적용.
          </div>
          <table className="w-full text-[10px]">
            <thead><tr className="text-gray-600 border-b border-[#1a2844]">
              <th className="text-left py-1.5 px-2">세대</th>
              <th className="text-right py-1.5 px-2">7대 실제</th>
              <th className="text-right py-1.5 px-2">6대 대비</th>
              <th className="text-left py-1.5 px-2">특이사항</th>
            </tr></thead>
            <tbody>
              {[
                ["20대", "52.0%", "+3.6%p", "전 연령 최저. 무응답 32% — 투표 참여가 변수"],
                ["30대", "54.3%", "+6.8%p", "6대 대비 최대 상승. 맘카페·신도시 효과"],
                ["40대", "58.6%", "+5.3%p", "핵심 지지층. 투표율 +5%p → 김경수 +0.26%p (민감도 1위)"],
                ["50대", "63.3%", "—", "안정적. 유권자 최대 규모 (55만)"],
                ["60대", "72.5%", "—", "보수 고투표율 고정층. 전체 투표율 견인"],
                ["70대+", "65.0%", "—", "70대 74.5% + 80+ 50.8% 가중평균"],
              ].map(([age, actual, delta, note], i) => (
                <tr key={i} className="border-b border-[#0e1825]">
                  <td className="py-1.5 px-2 text-gray-200 font-bold">{age}</td>
                  <td className="py-1.5 px-2 text-right text-cyan-400 font-bold font-mono">{actual}</td>
                  <td className={`py-1.5 px-2 text-right font-mono ${(delta as string).startsWith("+") ? "text-emerald-400" : "text-gray-500"}`}>{delta}</td>
                  <td className="py-1.5 px-2 text-gray-500 text-[9px]">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="bg-[#080d16] rounded-lg p-2.5 border border-[#1a2844] text-[9px] text-gray-400">
            <span className="text-cyan-400 font-bold">왜 보정하지 않는가:</span> 실시간 시그널(대통령효과, 접전도 등)은 투표율에 0.8~3%p 영향이나,
            격차에는 0.8%p 미만 영향. 불확실한 보정보다 7대 실제 데이터를 신뢰.
            투표율 변동은 시나리오(비관/동원/상승)에서 별도 분석.
          </div>
        </div>
      </div>

      {/* 변수 3: 지지율 */}
      <div className="wr-card">
        <div className="wr-card-header text-amber-400">변수 ③ 세대별 후보 지지율 (NESDC raw data)</div>
        <div className="px-4 py-3 space-y-2">
          <div className="text-[9px] text-gray-500">
            출처: NESDC 양자대결 연령별 교차분석 3개 조사 평균<br/>
            리얼미터/경남일보(26.01.24) + 서던포스트/KNN(26.03.03) + 여론조사꽃(26.03.19)
          </div>
          <table className="w-full text-[10px]">
            <thead><tr className="text-gray-600 border-b border-[#1a2844]">
              <th className="text-left py-1.5 px-2">세대</th>
              <th className="text-right py-1.5 px-2 text-blue-400">김경수</th>
              <th className="text-right py-1.5 px-2 text-red-400">박완수</th>
              <th className="text-right py-1.5 px-2 text-gray-500">무응답</th>
              <th className="text-right py-1.5 px-2 text-cyan-400">유효 김</th>
              <th className="text-left py-1.5 px-2">비고</th>
            </tr></thead>
            <tbody>
              {[
                ["20대", "29%", "39%", "32%", "44.9%", "무응답 최대 — 잠재 설득층"],
                ["30대", "42%", "36%", "22%", "54.2%", "김경수 우세. 맘카페/신도시"],
                ["40대", "61%", "23%", "16%", "71.3%", "핵심 지지층. 압도적 우세"],
                ["50대", "53%", "31%", "16%", "62.3%", "과반 확보. 이탈 방지 필수"],
                ["60대", "37%", "49%", "14%", "43.7%", "박완수 우세이나 설득 가능"],
                ["70대+", "27%", "58%", "15%", "33.4%", "보수 강고층"],
              ].map(([age, kim, park, und, eff, note], i) => (
                <tr key={i} className="border-b border-[#0e1825]">
                  <td className="py-1.5 px-2 text-gray-200 font-bold">{age}</td>
                  <td className="py-1.5 px-2 text-right text-blue-400 font-mono">{kim}</td>
                  <td className="py-1.5 px-2 text-right text-red-400 font-mono">{park}</td>
                  <td className="py-1.5 px-2 text-right text-gray-500 font-mono">{und}</td>
                  <td className="py-1.5 px-2 text-right text-cyan-400 font-bold font-mono">{eff}</td>
                  <td className="py-1.5 px-2 text-gray-500 text-[9px]">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="bg-[#080d16] rounded-lg p-2.5 border border-[#1a2844] text-[9px] text-gray-400">
            <span className="text-cyan-400 font-bold">무응답 처리 로직:</span> 무응답자 중 50%가 투표 참여, 투표하는 무응답자는 김:박 50:50 균등 배분.
            "유효 김"은 이 로직 적용 후 김경수 예상 득표율.
          </div>
        </div>
      </div>

      {/* 여론조사 vs 실제 투표 차이 */}
      <div className="wr-card">
        <div className="wr-card-header text-amber-400">무응답 처리가 왜 중요한가?</div>
        <div className="px-4 py-3 space-y-3">
          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
            <div className="text-[11px] text-gray-200 leading-relaxed">
              여론조사 무응답을 <span className="text-red-400 font-bold">전부 상대에게 배분</span>하면 격차 -21%p (박완수 압승)<br/>
              무응답을 <span className="text-cyan-400 font-bold">50:50 균등 배분</span>하면 격차 +2.3%p (김경수 근소 우세)<br/>
              → <span className="text-amber-400 font-bold">무응답 설득이 당락을 결정</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-blue-950/10 border border-blue-800/20 rounded-lg p-3">
              <div className="text-[9px] text-blue-400 font-bold mb-1">2030 무응답 22~32%</div>
              <div className="text-[10px] text-gray-300">
                투표율(52~54%) × 유효지지(44~54%)<br/>
                = 김경수 <span className="text-blue-400 font-bold">약 16만</span>
              </div>
            </div>
            <div className="bg-amber-950/10 border border-amber-800/20 rounded-lg p-3">
              <div className="text-[9px] text-amber-400 font-bold mb-1">4050 핵심 (유효 62~71%)</div>
              <div className="text-[10px] text-gray-300">
                투표율(59~63%) × 유효지지(62~71%)<br/>
                = 김경수 <span className="text-amber-400 font-bold">약 42만</span>
              </div>
            </div>
            <div className="bg-red-950/10 border border-red-800/20 rounded-lg p-3">
              <div className="text-[9px] text-red-400 font-bold mb-1">60+ (유효 34~57%)</div>
              <div className="text-[10px] text-gray-300">
                투표율(65~73%) × 유효지지(34~57%)<br/>
                = 박완수 <span className="text-red-400 font-bold">약 46만</span>
              </div>
            </div>
          </div>
          <div className="text-[10px] text-emerald-400 font-bold text-center">
            현재 모델: 김경수 51.2% vs 박완수 48.8% (격차 +2.3%p) — 초박빙 우세
          </div>
        </div>
      </div>

      {/* 승리 전략 보고서와의 교차 검증 */}
      <div className="wr-card">
        <div className="wr-card-header text-amber-400">승리 전략 보고서 교차 검증</div>
        <div className="px-4 py-3 space-y-2">
          <div className="text-[10px] text-gray-400 leading-relaxed">
            승리 전략 보고서 조건 vs 우리 모델 정량화. NESDC raw data + 무응답 균등배분 기반.
          </div>
          <table className="w-full text-[10px]">
            <thead><tr className="text-gray-600 border-b border-[#1a2844]">
              <th className="text-left py-1.5 px-2">보고서 내용</th>
              <th className="text-left py-1.5 px-2">우리 모델 검증</th>
              <th className="text-center py-1.5 px-2">일치</th>
            </tr></thead>
            <tbody>
              {[
                ["13~14만표를 잃고 시작", "무응답 전부 상대 배분 시 -21%p. 균등배분 시 +2.3%p → 무응답이 핵심", "✅"],
                ["김해/성산/거제 탈환 필수", "동부권 60%+ 필요 → 현재 55% 추정", "✅"],
                ["3040 투표율 극대화", "4050 유효지지 62~71%로 가장 효율적. 투표율 +5%p → +0.2%p", "✅"],
                ["뉴시니어 이탈 방지", "50대 유효 62.3% 확보 중. 이탈 시 타격 최대 (유권자 55만)", "✅"],
                ["이준석 표심 흡수", "20대 무응답 32% — 청년 설득이 격차를 좌우", "✅"],
              ].map(([report, model, match], i) => (
                <tr key={i} className="border-b border-[#0e1825]">
                  <td className="py-1.5 px-2 text-gray-300">{report}</td>
                  <td className="py-1.5 px-2 text-gray-400">{model}</td>
                  <td className="py-1.5 px-2 text-center text-emerald-400">{match}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 전략적 결론 */}
      <div className="wr-card border-t-2 border-t-emerald-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[12px] font-bold text-emerald-300">🎯 전략적 결론 — 모델이 말하는 승리 공식</h3>
          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
            <div className="text-[11px] text-gray-200 leading-[1.8]">
              "NESDC raw data 기반 현재 추세: <span className="text-emerald-400 font-bold">김경수 51.2% vs 박완수 48.8%</span> (초박빙 우세).<br/>
              단, 무응답 배분에 따라 결과가 뒤집힐 수 있음 — <span className="text-amber-400 font-bold">무응답 설득이 당락 결정</span>.<br/><br/>
              <span className="text-cyan-400 font-bold">핵심 전략 = 20대 무응답 설득 + 4050 지지 유지 + 60대 격차 축소</span>"
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-blue-950/10 border border-blue-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">최우선</div>
              <div className="text-[11px] text-blue-400 font-bold mt-0.5">20대 무응답 설득</div>
              <div className="text-[8px] text-gray-500 mt-0.5">32% 무응답 → 청년 정책 + SNS</div>
            </div>
            <div className="bg-amber-950/10 border border-amber-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">핵심</div>
              <div className="text-[11px] text-amber-400 font-bold mt-0.5">4050 지지 유지</div>
              <div className="text-[8px] text-gray-500 mt-0.5">유효 62~71% 사수 + 경제 공약</div>
            </div>
            <div className="bg-red-950/10 border border-red-800/20 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">보완</div>
              <div className="text-[11px] text-red-400 font-bold mt-0.5">60대 격차 축소</div>
              <div className="text-[8px] text-gray-500 mt-0.5">raw 37% → 유효 43.7% 확대</div>
            </div>
          </div>
        </div>
      </div>

      {/* 출처 */}
      <div className="wr-card">
        <div className="px-4 py-3">
          <div className="text-[8px] text-gray-600 space-y-0.5">
            <div className="font-bold mb-1">연구 출처</div>
            <div>📋 제9대 경남도지사 선거 승리 전략 보고서 (260315) — 세대별 인구 비중, 스윙 분석</div>
            <div>📊 중앙선관위 제7회 지방선거 투표율 분석 (2018) — 연령별 투표율 기저 (경남 65.8%)</div>
            <div>📰 <a href="https://www.hankookilbo.com/News/Read/201809181698071348" target="_blank" className="text-cyan-400 underline">한국일보 — 6·13 지방선거 30대 투표율 상승 폭 가장 컸다</a></div>
            <div>📊 <a href="https://www.nesdc.go.kr/portal/bbs/B0000005/view.do?nttId=17162&menuNo=200468" target="_blank" className="text-cyan-400 underline">NESDC — 리얼미터/경남일보 양자대결 교차분석 (26.01.24)</a></div>
            <div>📊 <a href="https://www.nesdc.go.kr/portal/bbs/B0000005/view.do?nttId=17574&menuNo=200468" target="_blank" className="text-cyan-400 underline">NESDC — 서던포스트/KNN 양자대결 교차분석 (26.03.03)</a></div>
            <div>📊 NESDC — 여론조사꽃 경남도지사 1000명 CATI 조사 (26.03.19)</div>
            <div>📄 <a href="https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001519807" target="_blank" className="text-cyan-400 underline">지방선거 투표율의 결정요인 연구 (KCI)</a></div>
            <div>📄 <a href="https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE02380495" target="_blank" className="text-cyan-400 underline">선거별 투표율 결정 요인 1987~2010 (한국정당학회보)</a></div>
            <div>📄 <a href="https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002934928" target="_blank" className="text-cyan-400 underline">2022 지방선거 투표행태 결정요인 (KCI)</a></div>
            <div>🌐 <a href="https://www.gsb.stanford.edu/insights/how-polls-influence-behavior" target="_blank" className="text-cyan-400 underline">How Polls Influence Behavior (Stanford GSB)</a></div>
            <div className="mt-1 text-gray-700">AI 기반 분석이며 참고용. 실제 투표 결과를 보장하지 않습니다.</div>
          </div>
        </div>
      </div>
    </>
  );
}


// ════════════════════════════════════════════════════════════════════
// TAB 3: 이벤트 임팩트 정량화 리서치
// ════════════════════════════════════════════════════════════════════

const EVENT_IMPACTS = [
  { type: "debate", icon: "🎙", label: "TV 토론", base: 2.0, range: [1.0, 5.0], lag: 6, decay: 14,
    evidence: "2022 대선 TV토론 → 윤석열 +3.2%p, 2017 대선 문재인 +4.1%p",
    age: { "20대": 1.3, "30대": 1.1, "40대": 1.0, "50대": 1.0, "60대": 0.8, "70+": 0.6 },
    strategy: "토론 직후 하이라이트 클립 → SNS 즉시 배포. 팩트체크 선제 대응. 맘카페 후기 유도." },
  { type: "scandal", icon: "⚠", label: "스캔들/위기", base: -2.5, range: [-1.0, -8.0], lag: 12, decay: 21,
    evidence: "김경수 사법리스크 프레임 → 지속적 -2~3%p 압력",
    age: { "20대": 1.4, "30대": 1.2, "40대": 1.0, "50대": 0.9, "60대": 0.7, "70+": 0.5 },
    strategy: "신속 해명 + 프레임 전환 (정책 이슈로). 침묵은 인정으로 해석됨." },
  { type: "policy", icon: "📋", label: "정책 발표", base: 1.5, range: [0.5, 3.0], lag: 24, decay: 7,
    evidence: "7대 지선 김경수 '경남형 일자리' → 지지율 +2.1%p (1주)",
    age: { "20대": 0.8, "30대": 1.2, "40대": 1.1, "50대": 1.0, "60대": 0.9, "70+": 0.7 },
    strategy: "핵심 공약 — 맘카페/신도시 타겟 확산 + 지역 언론 동시 배포." },
  { type: "gaffe", icon: "💬", label: "실언/실수", base: -1.5, range: [-0.5, -5.0], lag: 3, decay: 5,
    evidence: "2022 지선 실언 → SNS 밈화 → -1~3%p (바이럴 정도에 따라)",
    age: { "20대": 1.5, "30대": 1.2, "40대": 1.0, "50대": 0.8, "60대": 0.6, "70+": 0.4 },
    strategy: "상대 실언 시 — 클립 확산 + 반복 노출. 단, 과도한 네거티브는 역효과." },
  { type: "endorsement", icon: "🤝", label: "지지선언", base: 0.5, range: [0.2, 1.5], lag: 48, decay: 10,
    evidence: "민주노총 경남본부 지지선언 → 산업단지 투표율 +3%p 추정",
    age: { "20대": 0.5, "30대": 0.8, "40대": 1.2, "50대": 1.3, "60대": 1.0, "70+": 0.8 },
    strategy: "지지선언 후 조직 내부 동원 캠페인 연계. 해당 세대/지역 타겟 메시지." },
  { type: "visit", icon: "📍", label: "지역 방문", base: 0.3, range: [0.1, 1.0], lag: 24, decay: 3,
    evidence: "현장 방문은 지역 뉴스 1회 노출, 전도 효과는 제한적",
    age: { "20대": 0.3, "30대": 0.5, "40대": 0.8, "50대": 1.0, "60대": 1.5, "70+": 1.8 },
    strategy: "방문 후 사진/영상 → 지역 SNS 배포. 주민 증언 콘텐츠 제작." },
  { type: "sns", icon: "📱", label: "SNS 캠페인", base: 0.2, range: [0.1, 0.5], lag: 6, decay: 2,
    evidence: "바이럴 성공 시 검색량 +50~200%, 여론 직접 영향은 제한적",
    age: { "20대": 2.0, "30대": 1.5, "40대": 0.8, "50대": 0.4, "60대": 0.2, "70+": 0.1 },
    strategy: "초기 24시간 집중 부스팅. 리액션 지수 모니터링 후 2차 콘텐츠 결정." },
  { type: "poll", icon: "📊", label: "여론조사 발표", base: 0.0, range: [-2.0, 2.0], lag: 12, decay: 5,
    evidence: "Stanford 연구: 앞선 후보 → 편승효과 +1~2%p",
    age: { "20대": 1.2, "30대": 1.1, "40대": 1.0, "50대": 0.9, "60대": 0.7, "70+": 0.5 },
    strategy: "불리 시 '역전 가능' 프레임. 유리 시 편승효과 극대화." },
];

const SEVERITY_LABELS: Record<string, { label: string; mult: number }> = {
  critical: { label: "초대형", mult: 2.0 },
  major: { label: "대형", mult: 1.5 },
  standard: { label: "표준", mult: 1.0 },
  minor: { label: "소형", mult: 0.5 },
};

function EventImpactResearch() {
  const [severity, setSeverity] = useState("standard");
  const [expandedEvent, setExpandedEvent] = useState(null as string | null);
  const mult = SEVERITY_LABELS[severity]?.mult || 1.0;

  return (
    <>
      {/* 모델 개요 */}
      <div className="wr-card border-t-2 border-t-emerald-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[13px] font-bold text-emerald-300">🎯 이벤트 임팩트 정량화 모델</h3>
          <p className="text-[10px] text-gray-400 leading-relaxed">
            후보의 행동(정책 발표, TV 토론, 스캔들 등)이 여론조사에 미치는 영향을 유형별로 정량화합니다.
            학술 연구 + 과거 선거 사례 + 캠프 분석을 기반으로 예상 %p 변화를 추정합니다.
          </p>
          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
            <div className="text-[10px] text-cyan-400 font-mono text-center">
              예상 영향(%p) = 기저 임팩트 × 규모 승수 × 타이밍 × 미디어 × 반격 할인 × 접전도
            </div>
          </div>

          {/* 규모 선택 */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-500">규모 시뮬레이션:</span>
            <div className="flex rounded border border-[#1a2844] overflow-hidden">
              {Object.entries(SEVERITY_LABELS).map(([key, v]) => (
                <button key={key} onClick={() => setSeverity(key)}
                  className={`px-2.5 py-1 text-[9px] font-bold transition ${
                    severity === key ? "bg-emerald-600/30 text-emerald-400" : "text-gray-600 hover:text-gray-400"
                  }`}>{v.label} (×{v.mult})</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 임팩트 비교 차트 */}
      <div className="wr-card">
        <div className="wr-card-header">이벤트 유형별 예상 영향 비교</div>
        <div className="px-4 py-3 space-y-1.5">
          {EVENT_IMPACTS.map((ev) => {
            const impact = ev.base * mult;
            const maxAbs = 5 * mult;
            const barWidth = Math.min(100, (Math.abs(impact) / maxAbs) * 100);
            const isPositive = impact >= 0;

            return (
              <div key={ev.type}
                className="flex items-center gap-2 cursor-pointer hover:bg-white/[0.02] rounded px-1 py-1 transition"
                onClick={() => setExpandedEvent(expandedEvent === ev.type ? null : ev.type)}>
                <span className="text-base w-6 text-center">{ev.icon}</span>
                <span className="text-[10px] text-gray-300 w-20 shrink-0">{ev.label}</span>
                <div className="flex-1 flex items-center gap-1">
                  <div className="flex-1 h-4 bg-[#0a1020] rounded relative overflow-hidden">
                    {isPositive ? (
                      <div className="absolute left-1/2 top-0 bottom-0 bg-emerald-500/60 rounded-r"
                        style={{ width: `${barWidth / 2}%` }} />
                    ) : (
                      <div className="absolute top-0 bottom-0 bg-red-500/60 rounded-l"
                        style={{ width: `${barWidth / 2}%`, right: '50%' }} />
                    )}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className={`text-[9px] font-mono font-bold ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
                        {impact > 0 ? "+" : ""}{impact.toFixed(1)}%p
                      </span>
                    </div>
                  </div>
                </div>
                <span className="text-[8px] text-gray-600 w-24 text-right">
                  {(ev.range[0] * mult).toFixed(1)}~{(ev.range[1] * mult).toFixed(1)}%p
                </span>
                <span className="text-[10px] text-gray-600 w-4">{expandedEvent === ev.type ? "▼" : "▶"}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 선택된 이벤트 상세 */}
      {expandedEvent && (() => {
        const ev = EVENT_IMPACTS.find(e => e.type === expandedEvent);
        if (!ev) return null;
        const impact = ev.base * mult;
        return (
          <div className="wr-card border-l-2 border-l-emerald-500">
            <div className="px-4 py-3 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">{ev.icon}</span>
                <span className="text-[13px] font-bold text-gray-200">{ev.label}</span>
                <span className={`text-[11px] font-mono font-bold ${impact >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {impact > 0 ? "+" : ""}{impact.toFixed(1)}%p
                </span>
              </div>

              {/* 근거 */}
              <div className="bg-[#080d16] rounded-lg p-3">
                <div className="text-[9px] text-amber-400 font-bold uppercase tracking-widest mb-1">실증 근거</div>
                <div className="text-[10px] text-gray-400">{ev.evidence}</div>
              </div>

              {/* 시간 프로파일 */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
                  <div className="text-[8px] text-gray-600">반영 시차</div>
                  <div className="text-[14px] font-bold text-cyan-400 mt-0.5">{ev.lag}h</div>
                </div>
                <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
                  <div className="text-[8px] text-gray-600">피크</div>
                  <div className="text-[14px] font-bold text-amber-400 mt-0.5">T+{ev.lag + Math.floor(ev.decay * 24 / 4)}h</div>
                </div>
                <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
                  <div className="text-[8px] text-gray-600">효과 소멸</div>
                  <div className="text-[14px] font-bold text-gray-400 mt-0.5">{ev.decay}일</div>
                </div>
              </div>

              {/* 세대별 민감도 */}
              <div>
                <div className="text-[9px] text-gray-500 uppercase tracking-widest mb-1.5">세대별 민감도 (기저 대비 배율)</div>
                <div className="flex gap-1">
                  {Object.entries(ev.age).map(([age, ageMult]) => {
                    const h = Math.round(Math.min(40, (ageMult as number) * 20));
                    return (
                      <div key={age} className="flex-1 flex flex-col items-center">
                        <div className="w-full bg-[#0a1020] rounded-t relative" style={{ height: 40 }}>
                          <div className={`absolute bottom-0 w-full rounded-t ${(ageMult as number) > 1.0 ? "bg-emerald-500/40" : "bg-gray-700/40"}`}
                            style={{ height: h }} />
                        </div>
                        <div className="text-[8px] text-gray-500 mt-0.5">{age}</div>
                        <div className={`text-[8px] font-mono ${(ageMult as number) > 1.0 ? "text-emerald-400" : "text-gray-600"}`}>
                          ×{(ageMult as number).toFixed(1)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 전략 권고 */}
              <div className="bg-emerald-950/10 border border-emerald-800/20 rounded-lg p-3">
                <div className="text-[9px] text-emerald-400 font-bold uppercase tracking-widest mb-1">전략 권고</div>
                <div className="text-[10px] text-emerald-300/80 leading-relaxed">{ev.strategy}</div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* 승수 설명 */}
      <div className="wr-card">
        <div className="wr-card-header text-emerald-400">컨텍스트 승수 — 같은 이벤트도 상황에 따라 영향이 달라진다</div>
        <div className="px-4 py-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <div className="text-[9px] text-gray-500 font-bold">타이밍 승수</div>
              {[
                ["뉴스 공백기", "×1.3", "독점 노출 효과"],
                ["선거 임박 (D-30)", "×1.4", "관심 집중기"],
                ["주말", "×0.7", "뉴스 소비 감소"],
                ["대형 뉴스 경쟁", "×0.6", "묻힘 위험"],
              ].map(([name, mult, desc], i) => (
                <div key={i} className="flex items-center gap-2 text-[9px]">
                  <span className="text-cyan-400 font-mono w-8">{mult}</span>
                  <span className="text-gray-300">{name}</span>
                  <span className="text-gray-600 ml-auto">{desc}</span>
                </div>
              ))}
            </div>
            <div className="space-y-1.5">
              <div className="text-[9px] text-gray-500 font-bold">미디어/반격 승수</div>
              {[
                ["지상파 메인", "×1.5", "최대 노출"],
                ["포털 메인", "×1.3", "네이버 톱"],
                ["즉시 반격 당함", "×0.5", "효과 반감"],
                ["지역 한정", "×0.3", "전도 효과 제한"],
              ].map(([name, mult, desc], i) => (
                <div key={i} className="flex items-center gap-2 text-[9px]">
                  <span className="text-amber-400 font-mono w-8">{mult}</span>
                  <span className="text-gray-300">{name}</span>
                  <span className="text-gray-600 ml-auto">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 엔진 연동 설명 */}
      <div className="wr-card border-t-2 border-t-emerald-600">
        <div className="px-4 py-3 space-y-2">
          <h3 className="text-[12px] font-bold text-emerald-300">⚙ 엔진 연동 — Leading Index 자동 반영</h3>
          <div className="text-[10px] text-gray-400 leading-relaxed">
            이벤트가 감지되면 Leading Index의 <span className="text-cyan-400">issue_pressure</span> 컴포넌트에
            이벤트 유형별 가중치가 자동 적용됩니다. TV 토론(×1.5)은 지역 방문(×0.6)보다
            issue_pressure에 3배 더 큰 영향을 줍니다.
          </div>
          <div className="bg-[#080d16] rounded-lg p-3 text-[10px] text-gray-300 font-mono leading-relaxed">
            이벤트 감지 → event_type 분류<br/>
            → issue_pressure × event_weight 적용<br/>
            → Leading Index 재계산<br/>
            → 대시보드 알림 + 전략 권고
          </div>
          <div className="text-[8px] text-gray-600 border-t border-[#1a2844] pt-2">
            출처: KCI 유권자 투표행태 연구, Stanford GSB 여론조사 영향 연구, 2017/2022 대선 토론 효과 분석,
            캠프 내부 전략 보고서. API: /api/v2/event-impact?event_type=debate&severity=major
          </div>
        </div>
      </div>
    </>
  );
}


// ════════════════════════════════════════════════════════════════════
// TAB 4: 지역 언론 톤 트래킹 리서치
// ════════════════════════════════════════════════════════════════════

const REGIONAL_MEDIA_LIST = [
  // 방송
  { name: "KNN", domain: "knn.co.kr", type: "방송", tier: 1, influence: 1.5, desc: "경남방송 — 도민 시청률 1위" },
  { name: "MBC경남", domain: "mbc-gn.co.kr", type: "방송", tier: 1, influence: 1.4, desc: "MBC경남 — 양대 지역방송" },
  { name: "KBS창원", domain: "news.kbs.co.kr", type: "방송", tier: 1, influence: 1.3, desc: "KBS창원 — 여론조사 의뢰" },
  { name: "CJ경남방송", domain: "cj-gn.co.kr", type: "방송", tier: 2, influence: 0.7, desc: "CJ 경남 케이블" },
  // 종합일간
  { name: "경남신문", domain: "gnews.kr", type: "종합일간", tier: 1, influence: 1.3, desc: "경남 최대 일간지" },
  { name: "경남도민일보", domain: "idomin.com", type: "종합일간", tier: 1, influence: 1.2, desc: "진보 성향 지역지" },
  { name: "경남일보", domain: "gnnews.co.kr", type: "종합일간", tier: 1, influence: 1.1, desc: "보수 성향 지역지" },
  { name: "경남매일", domain: "gnmaeil.com", type: "경제", tier: 2, influence: 0.8, desc: "경남 경제 전문" },
  // 부산+경남 영향권
  { name: "부산일보", domain: "busan.com", type: "종합일간", tier: 1, influence: 1.3, desc: "부산일보 — 여론조사(KSOI) 의뢰" },
  { name: "국제신문", domain: "kookje.co.kr", type: "종합일간", tier: 1, influence: 1.1, desc: "국제신문 — 부산·경남 2대 일간지" },
  // 지역 신문
  { name: "창원시민신문", domain: "cwsm.kr", type: "지역", tier: 2, influence: 0.6, desc: "창원 지역 밀착" },
  { name: "거제신문", domain: "geojenews.co.kr", type: "지역", tier: 2, influence: 0.5, desc: "거제 지역" },
  { name: "김해뉴스", domain: "gimhaenews.co.kr", type: "지역", tier: 2, influence: 0.5, desc: "김해 지역" },
  { name: "진주신문", domain: "jinjunews.co.kr", type: "지역", tier: 2, influence: 0.6, desc: "진주 — 서부경남 핵심" },
  { name: "양산시민신문", domain: "yangsanilbo.com", type: "지역", tier: 2, influence: 0.6, desc: "양산 — 스윙 지역" },
  // 온라인
  { name: "뉴스경남", domain: "newsgyeongnam.kr", type: "온라인", tier: 2, influence: 0.5, desc: "경남 온라인" },
  { name: "경남연합일보", domain: "gnynews.co.kr", type: "온라인", tier: 2, influence: 0.4, desc: "경남 연합 온라인" },
  { name: "경남데일리", domain: "gnsdaily.kr", type: "온라인", tier: 2, influence: 0.4, desc: "경남 데일리" },
  { name: "뉴스사천", domain: "newssacheon.co.kr", type: "지역", tier: 2, influence: 0.4, desc: "사천 지역" },
  { name: "거창타임즈", domain: "gctnews.com", type: "지역", tier: 2, influence: 0.3, desc: "거창 지역" },
];

function RegionalMediaResearch() {
  return (
    <>
      {/* 개요 */}
      <div className="wr-card border-t-2 border-t-purple-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[13px] font-bold text-purple-300">📺 경남 지역 언론 톤 트래킹</h3>
          <p className="text-[10px] text-gray-400 leading-relaxed">
            경남 도민이 가장 많이 접하는 지역 매체(KNN, 경남신문, 경남도민일보 등)의 보도 톤을
            전국 언론과 분리하여 추적합니다. 지역 언론의 프레이밍이 도민 여론에 직접 영향을 미칩니다.
          </p>

          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
            <div className="text-[10px] text-cyan-400 font-mono text-center">
              지역 감성 = Σ(언론사별) [ 기사 감성 × 영향력 가중치 ] / 총 가중치
            </div>
          </div>
        </div>
      </div>

      {/* 왜 지역 언론이 중요한가 */}
      <div className="wr-card">
        <div className="wr-card-header text-purple-400">왜 지역 언론을 별도 추적하는가?</div>
        <div className="px-4 py-3 space-y-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#080d16] rounded-lg p-3">
              <div className="text-[9px] text-gray-500 font-bold mb-1.5">전국 언론</div>
              <div className="text-[10px] text-gray-400 space-y-1">
                <div>- 정치적 프레임 중심 (여당 vs 야당)</div>
                <div>- Horse Race 보도 (누가 앞서나)</div>
                <div>- 사법리스크 등 전국 이슈 집중</div>
                <div>- 경남 도민 일상과 괴리 가능</div>
              </div>
            </div>
            <div className="bg-purple-950/10 border border-purple-800/20 rounded-lg p-3">
              <div className="text-[9px] text-purple-400 font-bold mb-1.5">지역 언론</div>
              <div className="text-[10px] text-gray-300 space-y-1">
                <div>- 도민 생활 밀착 (교통, 교육, 복지)</div>
                <div>- 현직 도정 평가 (성과/비판)</div>
                <div>- 지역 경제 (조선업, 방산, 일자리)</div>
                <div>- 후보 지역 활동 직접 보도</div>
              </div>
            </div>
          </div>
          <div className="bg-amber-950/10 border border-amber-800/20 rounded-lg p-2.5 text-[10px] text-amber-300/80">
            핵심: 전국 언론이 부정적이어도 지역 언론이 우호적이면 도민 여론은 유지될 수 있고,
            그 반대도 성립합니다. 두 톤의 격차가 전략 조정의 시그널입니다.
          </div>
        </div>
      </div>

      {/* 경남 주요 언론사 */}
      <div className="wr-card">
        <div className="wr-card-header text-purple-400">경남 주요 언론사 + 영향력 가중치</div>
        <div className="px-4 py-3">
          <table className="w-full text-[10px]">
            <thead><tr className="text-gray-600 border-b border-[#1a2844]">
              <th className="text-left py-1.5 px-2">언론사</th>
              <th className="text-center py-1.5 px-2">유형</th>
              <th className="text-center py-1.5 px-2">티어</th>
              <th className="text-center py-1.5 px-2">가중치</th>
              <th className="text-left py-1.5 px-2">특성</th>
            </tr></thead>
            <tbody>
              {REGIONAL_MEDIA_LIST.map((m, i) => (
                <tr key={i} className="border-b border-[#0e1825]">
                  <td className="py-1.5 px-2 text-gray-200 font-bold">{m.name}</td>
                  <td className="py-1.5 px-2 text-center text-gray-400">{m.type}</td>
                  <td className="py-1.5 px-2 text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] ${
                      m.tier === 1 ? "bg-purple-950/40 text-purple-400" : "bg-gray-800 text-gray-500"
                    }`}>T{m.tier}</span>
                  </td>
                  <td className="py-1.5 px-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-16 h-1.5 bg-[#0a1020] rounded overflow-hidden">
                        <div className="h-full bg-purple-500/60 rounded" style={{ width: `${(m.influence / 1.5) * 100}%` }} />
                      </div>
                      <span className="text-gray-400 font-mono">x{m.influence}</span>
                    </div>
                  </td>
                  <td className="py-1.5 px-2 text-gray-500">{m.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 분석 방법론 */}
      <div className="wr-card">
        <div className="wr-card-header text-purple-400">분석 방법론</div>
        <div className="px-4 py-3 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">STEP 1</div>
              <div className="text-[11px] text-purple-400 font-bold mt-0.5">수집</div>
              <div className="text-[8px] text-gray-500 mt-0.5">네이버 뉴스 API<br/>도메인 필터링</div>
            </div>
            <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">STEP 2</div>
              <div className="text-[11px] text-purple-400 font-bold mt-0.5">감성 분석</div>
              <div className="text-[8px] text-gray-500 mt-0.5">기사별 긍정/부정/중립<br/>+ 지역 키워드 보정</div>
            </div>
            <div className="bg-[#080d16] rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-gray-600">STEP 3</div>
              <div className="text-[11px] text-purple-400 font-bold mt-0.5">가중 합산</div>
              <div className="text-[8px] text-gray-500 mt-0.5">영향력 x 감성<br/>→ 종합 톤 스코어</div>
            </div>
          </div>

          <div className="bg-[#080d16] rounded-lg p-3">
            <div className="text-[9px] text-gray-500 font-bold mb-1.5">지역 특화 감성 키워드 (기존 키워드에 추가)</div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-[8px] text-emerald-400 mb-0.5">긍정 (지역 발전)</div>
                <div className="text-[9px] text-gray-400">도민 지원, 지역 발전, 경남 투자, 일자리 창출, 조선 호황, 방산 수출, 청년 정주</div>
              </div>
              <div>
                <div className="text-[8px] text-red-400 mb-0.5">부정 (지역 위기)</div>
                <div className="text-[9px] text-gray-400">조선 위기, 산업 침체, 인구 유출, 지역 소외, 예산 삭감, 도정 비판, 행정 부실</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 전략적 활용 */}
      <div className="wr-card border-t-2 border-t-purple-600">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-[12px] font-bold text-purple-300">🎯 전략적 활용</h3>
          <div className="space-y-2">
            {[
              { signal: "지역 톤 > 전국 톤", meaning: "지역 밀착 전략 효과적", action: "지역 활동 강화, 로컬 이슈 집중" },
              { signal: "지역 톤 < 전국 톤", meaning: "지역 현안 불만 존재", action: "도정 비판 대응, 지역 공약 보강" },
              { signal: "특정 매체 부정 톤 강화", meaning: "해당 매체 프레이밍 주의", action: "매체 관계 관리, 반론 기고" },
              { signal: "지역 보도량 급증", meaning: "지역 이슈 부상", action: "즉시 대응 메시지 배포" },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 text-[10px] bg-[#080d16] rounded-lg p-2.5">
                <span className="text-purple-400 font-mono shrink-0 w-36">{item.signal}</span>
                <span className="text-gray-400 w-32 shrink-0">{item.meaning}</span>
                <span className="text-gray-300">{item.action}</span>
              </div>
            ))}
          </div>

          <div className="text-[8px] text-gray-600 border-t border-[#1a2844] pt-2">
            API: /api/v2/regional-media?keyword=김경수 | /api/v2/regional-media/compare (양 후보 비교)
          </div>
        </div>
      </div>
    </>
  );
}
