"use client";
import { useState } from "react";

// ════════════════════════════════════════════════════════════════════
// INDICES PAGE — 인덱스 설명서 + 일일 대시보드 + 추세 + 액션 임팩트
// "처음 보는 사람도 이해할 수 있어야 한다"
// ════════════════════════════════════════════════════════════════════

const INDICES = [
  {
    id: "leading",
    name: "판세지수",
    nameEn: "Pandse Index",
    icon: "🧭",
    color: "cyan",
    range: "0 ~ 100",
    neutral: "50 = 중립",
    description: "여론조사에 잡히지 않는 구조적·환경적 변수만으로 독립적인 판세를 예측하는 선행지표. 기본모델(실데이터)과 입력 데이터 중복 0건.",
    analogy: "기본모델이 '지금 점수'라면, 판세지수는 '경기 흐름'입니다. 실투표 다이내믹 예측에서 D-day 연동 가중치로 결합됩니다.",
    howToRead: [
      { condition: "60 이상", meaning: "김경수 압도 (+4%p 이상)", color: "text-emerald-400" },
      { condition: "55 ~ 60", meaning: "김경수 우세 (+2~4%p)", color: "text-emerald-400" },
      { condition: "50 ~ 55", meaning: "초박빙 김 근소 (0~+2%p)", color: "text-cyan-400" },
      { condition: "45 ~ 50", meaning: "초박빙 박 근소 (-2~0%p)", color: "text-gray-400" },
      { condition: "40 ~ 45", meaning: "박완수 우세 (-4~-2%p)", color: "text-red-400" },
      { condition: "40 이하", meaning: "박완수 압도 (-4%p 이하)", color: "text-red-400" },
    ],
    components: [
      { name: "대통령 효과 전이율", weight: "+1.8 (HIGH)", desc: "갤럽 대통령지지율 67%, 정당 민주39% vs 국힘27%. 경남 할인 적용" },
      { name: "후보 프리미엄 (정책)", weight: "+1.5 (HIGH)", desc: "부울경·경제·산업·청년 9개 키워드 이슈/리액션 자동계산" },
      { name: "여당 결집 + 전략적 투표", weight: "+0.7 (LOW)", desc: "KNN '국정안정 여당' 52.4%. D-day 근접 시 유동적" },
      { name: "투표율 차등 동원", weight: "+0.2 (MED)", desc: "탄핵 후 첫 지선. 진보 동원 미약 순효과" },
      { name: "현직 프리미엄", weight: "-1.5 (MED)", desc: "도정평가 긍정29%. 인지도·조직력 이점" },
      { name: "드루킹 잔여 효과", weight: "-1.2 (MED)", desc: "스캔들 반감기 18~24개월. 투표소 이탈 보정" },
      { name: "경남 보수 기저 회귀", weight: "-1.0 (HIGH)", desc: "6·7·8대 보수 평균 57%. 숨은 보수 투표소 회귀" },
      { name: "보수 결집 (위기감)", weight: "-0.8 (MED)", desc: "여당 압도 시 야당 위기감 동원. 60대 투표율 72.5%" },
    ],
    actionExample: "대통령지지율 하락 → 대통령효과 ↓ → 판세지수 하락 → 다이내믹 예측 악화",
    updateFreq: "팩터별 주간/격주 갱신 + 후보 프리미엄 매일 자동",
  },
  {
    id: "issue",
    name: "이슈 지수",
    nameEn: "Issue Index",
    icon: "🔥",
    color: "amber",
    range: "0 ~ 100",
    neutral: "키워드별 개별 산출",
    description: "특정 이슈가 '얼마나 터졌는가'를 측정합니다. 뉴스에 얼마나 나왔고, 얼마나 빨리 퍼지고 있는지.",
    analogy: "지진의 리히터 규모처럼, 이슈의 '크기'를 숫자로 보여줍니다.",
    howToRead: [
      { condition: "80+", meaning: "EXPLOSIVE — 전국 메인뉴스급", color: "text-red-400" },
      { condition: "60+", meaning: "HOT — 포털 상위, 커뮤니티 확산", color: "text-amber-400" },
      { condition: "40+", meaning: "ACTIVE — 관심 이슈, 모니터링 필요", color: "text-yellow-400" },
      { condition: "20+", meaning: "LOW — 소규모 보도", color: "text-gray-400" },
      { condition: "20 미만", meaning: "DORMANT — 사실상 비활성", color: "text-gray-600" },
    ],
    components: [
      { name: "뉴스 볼륨", weight: "25점", desc: "중복 제거 기사 수 (로그 스케일) + 네이버 검색 관심도" },
      { name: "확산 속도", weight: "30점", desc: "6시간/18시간 비율 + 네이버/구글 7일 변화율 + 급상승 보너스" },
      { name: "미디어 티어", weight: "20점", desc: "지상파 보도(+8), 포털 실검(+4), Tier1 기사 수" },
      { name: "후보 연결", weight: "15점", desc: "후보 직접 언급, 정책 연결, 지역 연결, 타겟 세대 관심" },
      { name: "채널 다양성", weight: "10점", desc: "뉴스/블로그/카페/영상/트렌드/커뮤니티 동시 확산" },
    ],
    actionExample: "공약 발표 → 뉴스 보도 → 검색 급등 → Issue Index 60+ (HOT)",
    updateFreq: "전략 갱신 시",
  },
  {
    id: "reaction",
    name: "반응 지수",
    nameEn: "Reaction Index",
    icon: "💬",
    color: "purple",
    range: "0 ~ 100",
    neutral: "direction: positive / negative / mixed",
    description: "이슈에 대해 사람들이 '어떻게 반응하는가'를 측정합니다. 찬성인지 반대인지, 확산되는지 묻히는지.",
    analogy: "이슈 지수가 '불이 났다'면, 반응 지수는 '사람들이 소방차를 부르는지, 구경하는지, 불을 키우는지'.",
    howToRead: [
      { condition: "75+", meaning: "VIRAL — 폭발적 확산, 밈화", color: "text-red-400" },
      { condition: "50+", meaning: "ENGAGED — 적극 참여, 콘텐츠 생산", color: "text-purple-400" },
      { condition: "25+", meaning: "RIPPLE — 관심은 있으나 깊이 부족", color: "text-blue-400" },
      { condition: "25 미만", meaning: "SILENT — 반응 없음", color: "text-gray-600" },
    ],
    components: [
      { name: "커뮤니티 공명", weight: "25점", desc: "22개 커뮤니티 동시 확산, 바이럴, 반복 빈도" },
      { name: "콘텐츠 생산", weight: "20점", desc: "블로그 글, 카페 토론, 유튜브 영상 제작 = 깊은 관여" },
      { name: "감성 방향", weight: "20점", desc: "긍정/부정 명확도 + 대상(우리/상대) + 톤(분노/지지/조롱)" },
      { name: "검색 반응", weight: "15점", desc: "구글/네이버 검색량 변화 = 일반 대중 관심" },
      { name: "직접 반응", weight: "20점", desc: "유튜브 댓글+좋아요 + 뉴스 댓글 + 동원 키워드" },
    ],
    actionExample: "상대 스캔들 → 커뮤니티 조롱 확산 → Rx 65 ENGAGED (negative, theirs)",
    updateFreq: "전략 갱신 시",
  },
  {
    id: "segment",
    name: "세그먼트 커버리지",
    nameEn: "Segment Coverage",
    icon: "🎯",
    color: "emerald",
    range: "0 ~ 100",
    neutral: "세대별 가중 평균",
    description: "우리 메시지가 핵심 타겟 유권자에게 얼마나 도달했는지 측정합니다. 30~50대가 핵심.",
    analogy: "마케팅의 '도달률'처럼, 이슈가 어느 세대까지 퍼졌는지 보여줍니다.",
    howToRead: [
      { condition: "70+", meaning: "EXCELLENT — 전 세대 고른 도달", color: "text-emerald-400" },
      { condition: "50+", meaning: "GOOD — 대부분 도달, 일부 GAP", color: "text-cyan-400" },
      { condition: "30+", meaning: "PARTIAL — 특정 세대만 반응", color: "text-amber-400" },
      { condition: "30 미만", meaning: "WEAK — 타겟 미도달", color: "text-red-400" },
    ],
    components: [
      { name: "20대", weight: "10%", desc: "인구 10%. 투표율 낮지만 SNS 확산력 큼" },
      { name: "30대", weight: "20%", desc: "신도시 핵심. 맘카페/온라인 여론 형성" },
      { name: "40대", weight: "25%", desc: "핵심 허리층. 노동/교육/경제 민감" },
      { name: "50대", weight: "25%", desc: "최대 유권자. 스윙 가능, 이탈 방지 핵심" },
      { name: "60대+", weight: "17%", desc: "보수 고정층. 변심 적으나 수가 많음" },
    ],
    actionExample: "맘카페 공략 → 30대 커버리지 68% → 하지만 50대 13% → GAP 보완 필요",
    updateFreq: "전략 갱신 시",
  },
  {
    id: "attribution",
    name: "귀인 신뢰도",
    nameEn: "Attribution Confidence",
    icon: "🔗",
    color: "blue",
    range: "0 ~ 1.0",
    neutral: "높을수록 '우리 행동 = 결과' 확실",
    description: "우리가 한 행동(공약 발표, 방문 등)이 실제로 여론 변화를 만들었는지, 인과관계의 확실성을 측정합니다.",
    analogy: "광고비를 썼는데 매출이 올랐다면, '그 광고 때문인가 다른 이유인가'를 판별하는 것.",
    howToRead: [
      { condition: "0.6+", meaning: "강한 귀인 — 우리 행동이 반응을 만들었을 가능성 높음", color: "text-emerald-400" },
      { condition: "0.4 ~ 0.6", meaning: "보통 — 일부 연결 확인, 다른 요인도 존재", color: "text-amber-400" },
      { condition: "0.2 ~ 0.4", meaning: "약한 귀인 — 연결 불확실", color: "text-gray-400" },
      { condition: "0.2 미만", meaning: "귀인 불가 — 반응이 우리 행동과 무관할 가능성", color: "text-red-400" },
    ],
    components: [
      { name: "키워드 매칭", weight: "30%", desc: "행동 키워드와 반응 키워드 일치" },
      { name: "반응 깊이", weight: "25%", desc: "커뮤니티 공명, 바이럴, 감성 극단값" },
      { name: "테마 매칭", weight: "15%", desc: "'경제→일자리' 등 의미적 그룹 매칭" },
      { name: "지역 매칭", weight: "15%", desc: "행동 지역과 반응 집중 지역 일치" },
      { name: "시간 가중", weight: "×배율", desc: "행동 직후(×1.0) → 72시간 후(×0.2)" },
    ],
    actionExample: "'AI 대전환 공약' 발표 → 클리앙/맘카페 반응 → 키워드 일치 + 30대 반응 → 0.62",
    updateFreq: "전략 갱신 시",
  },
  {
    id: "forecast",
    name: "지지율 예측",
    nameEn: "Support Forecast",
    icon: "📊",
    color: "red",
    range: "0 ~ 100%",
    neutral: "여론조사와 비교하여 오차를 줄이는 것이 목표",
    description: "현재 모든 시그널을 종합하여 실제 투표 시 예상 득표율을 추정합니다. 여론조사와 다를 수 있습니다.",
    analogy: "여론조사가 '온도계'라면, 예측 모델은 '내일 날씨 예보'. 더 많은 데이터로 미래를 예측합니다.",
    howToRead: [
      { condition: "오차 2%p 이내", meaning: "정확한 예측 — 모델 신뢰 가능", color: "text-emerald-400" },
      { condition: "오차 2~5%p", meaning: "보통 — 참고 수준", color: "text-amber-400" },
      { condition: "오차 5%p 이상", meaning: "부정확 — 모델 재검토 필요", color: "text-red-400" },
    ],
    components: [
      { name: "기저 예측", weight: "기본", desc: "최근 여론조사 추세 + 모멘텀" },
      { name: "선행지수", weight: "보정", desc: "Leading Index로 미래 방향 보정" },
      { name: "투표율 모델", weight: "보정", desc: "세대별 투표율 차이 반영 (38:38 → 42:58)" },
      { name: "이벤트 임팩트", weight: "보정", desc: "예정된 이벤트의 예상 영향 반영" },
    ],
    actionExample: "여론조사 38:38 + 투표율 구조 = 실제 42:58 예측. 목표: 이 예측의 정확도를 높이는 것.",
    updateFreq: "일 1회",
  },
  {
    id: "turnout",
    name: "투표율 예측",
    nameEn: "Turnout Prediction",
    icon: "🗳",
    color: "amber",
    range: "김경수 % : 박완수 %",
    neutral: "gap 양수 = 김경수 유리",
    description: "세대별 인구 × 투표율 × 지지율을 교차하여, 실제 투표함을 열었을 때의 결과를 추정합니다.",
    analogy: "여론조사가 '누구를 지지하세요?'라면, 이 모델은 '실제로 투표장에 가는 사람만 세면?'",
    howToRead: [
      { condition: "gap +5%p 이상", meaning: "김경수 승리 예상", color: "text-emerald-400" },
      { condition: "gap ±5%p", meaning: "초박빙 — 투표율이 결과를 결정", color: "text-amber-400" },
      { condition: "gap -5%p 이상", meaning: "박완수 우세 — 투표율 반전 필요", color: "text-red-400" },
    ],
    components: [
      { name: "세대별 인구", weight: "고정", desc: "경남 263만 유권자의 세대 분포" },
      { name: "투표율 추정", weight: "동적", desc: "8대 기저선 + 대통령효과/접전/동원 보정" },
      { name: "지지율 추정", weight: "동적", desc: "7대 패턴 70% + 현재 환경 20% + 8대 참조 10%" },
      { name: "시나리오", weight: "5개", desc: "비관 / 기저 / 3040동원 / 접전효과 / 최적" },
    ],
    actionExample: "현재 추세 42:58 → 3040 동원 시 44:56 → 전면 동원 시 46:54 접근",
    updateFreq: "일 1회",
  },
];

// ════════════════════════════════════════════════════════════════════
// 10개 인덱스 총정리 (파이프라인 레이어 기준)
// ════════════════════════════════════════════════════════════════════

const INDEX_TABLE = [
  { n: 1, name: "Issue Index", range: "0~100", layer: "L1 Trigger", brief: "이슈가 얼마나 크고 빠른가", color: "text-amber-400" },
  { n: 2, name: "Reaction Index", range: "0~100", layer: "L2 Reaction", brief: "사람들이 얼마나 깊게 반응하는가", color: "text-purple-400" },
  { n: 3, name: "Segment Estimate", range: "conf 0~1", layer: "L3 Structure", brief: "누가 반응하는가 (연령/성별/성향)", color: "text-emerald-400" },
  { n: 4, name: "VoterSegment Priority", range: "0~1", layer: "L3 Structure", brief: "어느 지역이 전략적으로 중요한가", color: "text-emerald-400" },
  { n: 5, name: "OrgSignal Influence", range: "0~100", layer: "L3 Structure", brief: "어떤 조직이 얼마나 영향력 있게 움직이는가", color: "text-emerald-400" },
  { n: 6, name: "Attribution Confidence", range: "0~1", layer: "L4 Attribution", brief: "우리 행동이 반응을 만들었는가", color: "text-blue-400" },
  { n: 7, name: "Leading Index", range: "0~100", layer: "L5 Index", brief: "종합적으로 흐름이 유리한가", color: "text-cyan-400" },
  { n: 8, name: "Lag Correlation", range: "r -1~+1", layer: "L6 Polling", brief: "선행지수가 여론조사를 선행하는가", color: "text-gray-400" },
  { n: 9, name: "Support Forecast", range: "+--%p", layer: "L7 Forecast", brief: "지지율이 어떻게 변할 것인가", color: "text-red-400" },
  { n: 10, name: "Feedback Accuracy", range: "0~100%", layer: "L8 Learning", brief: "전략 정확도가 개선되고 있는가", color: "text-purple-400" },
];

// ════════════════════════════════════════════════════════════════════
// 파이프라인 단계 정의 (실제 데이터 흐름)
// ════════════════════════════════════════════════════════════════════

const PIPELINE_STEPS = [
  {
    step: 0, layer: "PRE-TRIGGER", color: "text-red-400", borderColor: "border-l-red-500",
    sources: "경남도청 보도자료 + 상대 SNS + 기자단 시그널",
    output: '"민생지원금 선점 위험!" CRITICAL 경고',
    action: "즉시 선제 대응 검토",
    engine: "pretrigger_collector.py → 4채널 감시, 17개 정책 선점 키워드",
  },
  {
    step: 1, layer: "TRIGGER → Issue Index", color: "text-amber-400", borderColor: "border-l-amber-500",
    sources: "네이버뉴스 + 중복제거 + anomaly + 구글/네이버 트렌드",
    output: '"경남 청년정책" 65점 [HOT]',
    action: "확산속도(30) + 뉴스볼륨(25) + 미디어티어(20) + 후보연결(15) + 채널다양성(10)",
    engine: "issue_index.py → 5-component, 네이버 관심도 보조, 세대 피크 보너스",
  },
  {
    step: 2, layer: "REACTION → Reaction Index", color: "text-purple-400", borderColor: "border-l-purple-500",
    sources: "커뮤니티 22곳 + YT댓글/좋아요 + 뉴스댓글 + AI 감성 + 네이버 검색",
    output: "Rx 51점 [ENGAGED] direction: positive, 신뢰 80%",
    action: "velocity bonus x1.1 적용",
    engine: "reaction_index.py → 5-Layer + 뉴스댓글 보조 + YT 좋아요/조회수",
  },
  {
    step: 3, layer: "STRUCTURE", color: "text-emerald-400", borderColor: "border-l-emerald-500",
    sources: "커뮤니티 프록시 + 네이버 DataLab + 18개 시군 + 25개 조직",
    output: '세그먼트: "3040 학부모 반응" | 지역: "창원 0.776" | 조직: "민주노총 48"',
    action: "Segment Coverage Score: 34.2 [PARTIAL] — 50대 GAP",
    engine: "segment_mapper.py + org_signal_detector.py + tenant_config.py",
  },
  {
    step: 4, layer: "ATTRIBUTION", color: "text-blue-400", borderColor: "border-l-blue-500",
    sources: "후보 행동 로그 + 반응 before/after 스냅샷",
    output: '"청년정책 PUSH → 맘카페 반응 +23" confidence 0.7',
    action: "시간 가중(72h decay) + 의미적 테마 매칭 + 상대 행동 할인",
    engine: "reaction_attribution.py → 5-factor 신뢰도 + counter-attribution",
  },
  {
    step: 5, layer: "LEADING INDEX", color: "text-cyan-400", borderColor: "border-l-cyan-500",
    sources: "9-component 가중 합산 + 이벤트 가중치",
    output: "53.2 (stable, 약간 유리) — driver: reaction_index(+9.1)",
    action: "issue(15%) + anomaly(10%) + reaction(15%) + social(10%) + poll(20%) + 이슈idx(12%) + 반응idx(13%) + 대통령효과(8%) + 경제(5%)",
    engine: "leading_index_engine.py → event_context 자동 감지, 스냅샷 저장",
  },
  {
    step: 6, layer: "POLLING + LAG", color: "text-gray-400", borderColor: "border-l-gray-500",
    sources: "여론조사 시계열 + Leading Index 시계열",
    output: "여론조사 7건 → 승률 62.1% | lag r=0.0 (데이터 축적 중)",
    action: "선행지수가 여론조사를 며칠 앞서 예측하는지 상관 분석",
    engine: "polling_tracker.py + lag_correlator.py",
  },
  {
    step: 7, layer: "FORECAST", color: "text-red-400", borderColor: "border-l-red-500",
    sources: "Leading Index + 투표율 모델 + 이벤트 임팩트",
    output: "격차 +0.0%p 예상 | Bear -0.5 / Base 0.0 / Bull +0.3",
    action: "투표율 모델: 38:38 → 실제 42:58 (세대별 교차)",
    engine: "forecast_engine.py + turnout_predictor.py + event_impact.py",
  },
  {
    step: 8, layer: "LEARNING", color: "text-purple-400", borderColor: "border-l-purple-500",
    sources: "예측 vs 여론조사 실제값 비교",
    output: "이번 주 정확도 68% (상승 6%) | push 75% → confidence 상향",
    action: "오차 패턴 학습 → 다음 사이클 strategy_mode에 자동 반영",
    engine: "learning_feedback.py + index_tracker.py → AI 학습 누적",
  },
];


// ════════════════════════════════════════════════════════════════════

export function IndicesPage() {
  const [expandedIndex, setExpandedIndex] = useState(null as string | null);
  const [tab, setTab] = useState("guide");

  return (
    <div className="space-y-3 max-w-5xl mx-auto">
      {/* Header + Tabs */}
      <div className="wr-card border-t-2 border-t-cyan-600">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[14px] font-bold text-cyan-300">📈 인덱스</h2>
            <div className="flex rounded border border-[#1a2844] overflow-hidden">
              <button onClick={() => setTab("guide")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "guide" ? "bg-cyan-600/30 text-cyan-400" : "text-gray-600 hover:text-gray-400"
                }`}>인덱스 설명서</button>
              <button onClick={() => setTab("pipeline")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "pipeline" ? "bg-amber-600/30 text-amber-400" : "text-gray-600 hover:text-gray-400"
                }`}>파이프라인 흐름</button>
              <button onClick={() => setTab("summary")}
                className={`px-3 py-1 text-[9px] font-bold transition ${
                  tab === "summary" ? "bg-emerald-600/30 text-emerald-400" : "text-gray-600 hover:text-gray-400"
                }`}>10개 인덱스 총정리</button>
            </div>
          </div>
          <p className="text-[10px] text-gray-500 leading-relaxed">
            {tab === "guide" && "각 지표의 의미, 구성요소, 읽는 법. 처음 보는 사람도 3분 안에 이해할 수 있도록."}
            {tab === "pipeline" && "데이터가 흐르는 순서. Pre-Trigger → Trigger → Reaction → Structure → Attribution → Index → Polling → Forecast → Learning."}
            {tab === "summary" && "10개 인덱스 한눈에. 레이어별 역할과 범위."}
          </p>
        </div>
      </div>

      {/* ══════════ TAB 1: 인덱스 설명서 ══════════ */}
      {tab === "guide" && (
      <>
        {INDICES.map((idx) => {
          const isExpanded = expandedIndex === idx.id;
          return (
            <div key={idx.id} className={`wr-card transition-all ${isExpanded ? "border-l-2 border-l-cyan-500" : ""}`}>
              <div className="px-4 py-3 cursor-pointer hover:bg-white/[0.02] transition"
                onClick={() => setExpandedIndex(isExpanded ? null : idx.id)}>
                <div className="flex items-center gap-3">
                  <span className="text-xl">{idx.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-bold text-gray-200">{idx.name}</span>
                      <span className="text-[9px] text-gray-600">{idx.nameEn}</span>
                      <span className="text-[8px] text-gray-700 font-mono ml-auto">{idx.range}</span>
                    </div>
                    <div className="text-[10px] text-gray-500 mt-0.5">{idx.description}</div>
                  </div>
                  <span className="text-[10px] text-gray-600">{isExpanded ? "▼" : "▶"}</span>
                </div>
              </div>
              {isExpanded && (
                <div className="px-4 pb-4 space-y-3">
                  <div className="bg-cyan-950/10 border border-cyan-800/20 rounded-lg p-2.5">
                    <div className="text-[9px] text-cyan-400 font-bold mb-0.5">쉽게 말하면</div>
                    <div className="text-[10px] text-cyan-300/80">{idx.analogy}</div>
                  </div>
                  <div>
                    <div className="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1.5">어떻게 읽나요?</div>
                    <div className="space-y-1">
                      {idx.howToRead.map((h, i) => (
                        <div key={i} className="flex items-center gap-3 text-[10px]">
                          <span className={`font-mono font-bold w-24 shrink-0 ${h.color}`}>{h.condition}</span>
                          <span className="text-gray-300">{h.meaning}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1.5">구성요소</div>
                    <table className="w-full text-[10px]"><tbody>
                      {idx.components.map((c, i) => (
                        <tr key={i} className="border-b border-[#0e1825]">
                          <td className="py-1.5 pr-2 text-gray-200 font-bold w-28">{c.name}</td>
                          <td className="py-1.5 pr-2 text-cyan-400 font-mono w-16">{c.weight}</td>
                          <td className="py-1.5 text-gray-500">{c.desc}</td>
                        </tr>
                      ))}
                    </tbody></table>
                  </div>
                  <div className="bg-[#080d16] rounded-lg p-2.5">
                    <div className="text-[9px] text-amber-400 font-bold mb-0.5">행동 → 지표 변화 예시</div>
                    <div className="text-[10px] text-gray-300 font-mono">{idx.actionExample}</div>
                  </div>
                  <div className="text-[8px] text-gray-600 flex justify-between border-t border-[#1a2844] pt-2">
                    <span>업데이트: {idx.updateFreq}</span>
                    <span>API: /api/v2/index-daily</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* 운영 5원칙 */}
        <div className="wr-card border-t-2 border-t-amber-600">
          <div className="px-4 py-3 space-y-2">
            <h3 className="text-[12px] font-bold text-amber-300">📐 지표 운영 5원칙</h3>
            {[
              { n: "1", t: "근거와 설명", d: "모든 지표는 데이터 소스와 계산 근거가 명시. 블랙박스 없음.", c: "text-cyan-400" },
              { n: "2", t: "이해 용이성", d: "처음 보는 사람도 3분 안에 이해. 비유와 예시를 붙임.", c: "text-emerald-400" },
              { n: "3", t: "매일 측정·저장", d: "매일 스냅샷 저장, 차트로 추세 확인.", c: "text-blue-400" },
              { n: "4", t: "액션 임팩트", d: "행동이 지표를 움직였는지 확인. 효과 없으면 전략 재검토 + 대안 제안.", c: "text-amber-400" },
              { n: "5", t: "AI 학습", d: "예측 vs 실제 비교 → 오차 학습 → 모델 보정. 목표: 여론조사보다 정확한 예측.", c: "text-purple-400" },
            ].map((p) => (
              <div key={p.n} className="flex gap-3 items-start bg-[#080d16] rounded-lg p-2.5">
                <span className={`text-[14px] font-black ${p.c} w-6 text-center shrink-0`}>{p.n}</span>
                <div><span className={`text-[10px] font-bold ${p.c}`}>{p.t}</span><span className="text-[10px] text-gray-400 ml-2">{p.d}</span></div>
              </div>
            ))}
          </div>
        </div>
      </>
      )}

      {/* ══════════ TAB 2: 파이프라인 흐름 ══════════ */}
      {tab === "pipeline" && (
      <>
        <div className="wr-card">
          <div className="wr-card-header text-amber-400">9-Flow Election Training Model — 데이터가 흐르는 순서</div>
          <div className="px-4 py-3 space-y-0">
            {PIPELINE_STEPS.map((s, i) => (
              <div key={s.step}>
                {/* Step card */}
                <div className={`border-l-2 ${s.borderColor} pl-3 py-2.5`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[11px] font-black ${s.color} font-mono`}>[{s.step}]</span>
                    <span className={`text-[12px] font-bold ${s.color}`}>{s.layer}</span>
                  </div>
                  <div className="ml-6 space-y-1">
                    <div className="text-[9px] text-gray-500">{s.sources}</div>
                    <div className="text-[10px] text-gray-200">→ {s.output}</div>
                    <div className="text-[9px] text-gray-400">→ {s.action}</div>
                    <div className="text-[8px] text-gray-700 font-mono">{s.engine}</div>
                  </div>
                </div>
                {/* Arrow */}
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="flex items-center pl-4 py-0.5">
                    <span className="text-[10px] text-gray-700">↓</span>
                  </div>
                )}
              </div>
            ))}
            {/* Loop back */}
            <div className="border-l-2 border-l-gray-700 pl-3 py-2">
              <div className="text-[10px] text-gray-600 font-mono">↻ [0] PRE-TRIGGER (다음 사이클)</div>
            </div>
          </div>
        </div>

        {/* 엔진 커버리지 */}
        <div className="wr-card border-t-2 border-t-emerald-600">
          <div className="wr-card-header text-emerald-400">여론 영향 7요인 × 엔진 연결 상태</div>
          <div className="px-4 py-3 space-y-1">
            {[
              { icon: "🏛", name: "중앙정치", pipeline: "national_poll → 대통령효과(8%)", layer: "L5 Index" },
              { icon: "🎯", name: "이벤트", pipeline: "event_context → issue_pressure 가중", layer: "L1+L5" },
              { icon: "📺", name: "미디어", pipeline: "AI 감성 + 지역 8개 언론 → reaction", layer: "L2+L5" },
              { icon: "💰", name: "경제", pipeline: "6개 지표 → economy(5%)", layer: "L5 Index" },
              { icon: "🏗", name: "조직", pipeline: "25개 단체 → endorsement → reaction", layer: "L2+L3" },
              { icon: "⚔", name: "상대행동", pipeline: "Pre-Trigger 4채널 → CRITICAL 경고", layer: "L0 Pre" },
              { icon: "🗳", name: "투표율", pipeline: "세대별 교차 모델 5시나리오", layer: "L7 Forecast" },
            ].map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px] py-1 px-1 rounded hover:bg-white/[0.02]">
                <span className="w-5 text-center">{f.icon}</span>
                <span className="text-gray-300 w-16 shrink-0 font-bold">{f.name}</span>
                <span className="text-emerald-500 text-[9px]">●</span>
                <span className="text-gray-500 text-[9px] flex-1">{f.pipeline}</span>
                <span className="text-[8px] text-gray-700 font-mono">{f.layer}</span>
              </div>
            ))}
            <div className="flex items-center justify-between pt-1.5 border-t border-[#0e1825]">
              <span className="text-[9px] text-emerald-400 font-bold">7/7 파이프라인 연결 완료</span>
              <span className="text-[8px] text-gray-600">매일 자동 실행 → 스냅샷 저장 → 추세 차트</span>
            </div>
          </div>
        </div>
      </>
      )}

      {/* ══════════ TAB 3: 10개 인덱스 총정리 ══════════ */}
      {tab === "summary" && (
      <>
        <div className="wr-card">
          <div className="wr-card-header text-emerald-400">10개 인덱스 총정리</div>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-gray-600 border-b border-[#1a2844]">
                  <th className="text-center py-2 px-2 w-8">#</th>
                  <th className="text-left py-2 px-2">Index</th>
                  <th className="text-center py-2 px-2">범위</th>
                  <th className="text-center py-2 px-2">Layer</th>
                  <th className="text-left py-2 px-3">핵심 한줄</th>
                </tr>
              </thead>
              <tbody>
                {INDEX_TABLE.map((idx) => (
                  <tr key={idx.n} className="border-b border-[#0e1825] hover:bg-white/[0.02]">
                    <td className="text-center py-2 px-2 text-gray-600 font-mono">{idx.n}</td>
                    <td className={`py-2 px-2 font-bold ${idx.color}`}>{idx.name}</td>
                    <td className="text-center py-2 px-2 text-gray-500 font-mono">{idx.range}</td>
                    <td className="text-center py-2 px-2">
                      <span className={`text-[8px] px-1.5 py-0.5 rounded ${
                        idx.layer.includes("Trigger") ? "bg-amber-950/30 text-amber-400" :
                        idx.layer.includes("Reaction") ? "bg-purple-950/30 text-purple-400" :
                        idx.layer.includes("Structure") ? "bg-emerald-950/30 text-emerald-400" :
                        idx.layer.includes("Attribution") ? "bg-blue-950/30 text-blue-400" :
                        idx.layer.includes("Index") ? "bg-cyan-950/30 text-cyan-400" :
                        idx.layer.includes("Polling") ? "bg-gray-800 text-gray-400" :
                        idx.layer.includes("Forecast") ? "bg-red-950/30 text-red-400" :
                        "bg-purple-950/30 text-purple-400"
                      }`}>{idx.layer}</span>
                    </td>
                    <td className="py-2 px-3 text-gray-300">{idx.brief}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 예측 경쟁 목표 */}
        <div className="wr-card border-t-2 border-t-red-600">
          <div className="px-4 py-3 space-y-2">
            <h3 className="text-[12px] font-bold text-red-300">🏆 궁극적 목표 — 여론조사와의 예측 경쟁</h3>
            <div className="text-[10px] text-gray-400 leading-relaxed">
              10개 인덱스가 매일 축적되면, AI가 패턴을 학습하여 <span className="text-cyan-400">여론조사보다 먼저, 더 정확하게</span> 판세를 예측합니다.
              매주 여론조사가 나올 때마다 우리 예측과 비교하여 오차를 기록하고, 모델을 보정합니다.
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { phase: "Phase 1", target: "오차 5%p 이내", desc: "데이터 축적", color: "text-gray-300" },
                { phase: "Phase 2", target: "오차 3%p 이내", desc: "학습 보정", color: "text-amber-300" },
                { phase: "Phase 3", target: "오차 2%p 이내", desc: "여론조사 대체", color: "text-emerald-300" },
              ].map((p, i) => (
                <div key={i} className="bg-[#080d16] rounded-lg p-2.5 text-center">
                  <div className="text-[8px] text-gray-600">{p.phase}</div>
                  <div className={`text-[11px] font-bold mt-0.5 ${p.color}`}>{p.target}</div>
                  <div className="text-[8px] text-gray-500 mt-0.5">{p.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 데이터 흐름 요약 */}
        <div className="wr-card">
          <div className="wr-card-header text-cyan-400">데이터 흐름 요약</div>
          <div className="px-4 py-3">
            <div className="bg-[#080d16] rounded-lg p-3 text-[10px] font-mono text-gray-300 leading-[2.2]">
              <span className="text-red-400">[0] Pre-Trigger</span> — 상대 행동 사전 감지<br/>
              <span className="text-amber-400">[1] Issue Index</span> — 이슈 크기/속도 측정<br/>
              <span className="text-purple-400">[2] Reaction Index</span> — 반응 깊이/방향 측정<br/>
              <span className="text-emerald-400">[3] Structure</span> — 세그먼트 + 지역 + 조직<br/>
              <span className="text-blue-400">[4] Attribution</span> — 행동-반응 인과관계<br/>
              <span className="text-cyan-400">[5] Leading Index</span> — 9-component 종합 선행지수<br/>
              <span className="text-gray-400">[6] Polling + Lag</span> — 여론조사 + 선행 상관<br/>
              <span className="text-red-400">[7] Forecast</span> — 지지율 예측 + 투표율 모델<br/>
              <span className="text-purple-400">[8] Learning</span> — 예측 vs 실제 → AI 학습 → 보정<br/>
              <span className="text-gray-600">↻ 다음 사이클로 반복</span>
            </div>
          </div>
        </div>
      </>
      )}
    </div>
  );
}
