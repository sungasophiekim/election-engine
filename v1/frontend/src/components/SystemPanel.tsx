"use client";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";

const TABS = ["이슈지수", "반응지수", "판세지수"] as const;
type Tab = (typeof TABS)[number];

function SourceRow({ name, updatedAt }: { name: string; updatedAt?: string }) {
  const ts = fmtTs(updatedAt);
  const isLive = ts.includes("분 전") && parseInt(ts) < 15;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[#121e33] last:border-0">
      <span className="text-[10px] text-gray-300">{name}</span>
      <span className={`text-[9px] font-mono ${ts === "—" ? "text-gray-600" : "text-gray-400"}`}>{ts}</span>
    </div>
  );
}

function IssueTab({ indices }: { indices: any }) {
  const issue = indices?.issue;
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">지표 설명</div>
        <p className="text-[10px] text-gray-400 leading-relaxed">
          미디어에서 어느 쪽이 유리한 이슈를 점유하고 있는지를 측정하는 가중지수입니다.
          광역 뉴스 수집(~250건) → AI 클러스터링(TOP 10 이슈) → 진영 판단 → 기사수 x 감성강도로 가중 점수화.
          50pt = 중립, &gt;50 우리 유리, &lt;50 상대 유리.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">산출 방식</div>
        <div className="space-y-1">
          {[
            { name: "광역 뉴스 수집", desc: "11개 쿼리로 경남 관련 뉴스 ~250건 수집 (Naver News API)" },
            { name: "AI 클러스터링", desc: "Claude Haiku가 사건별 TOP 10 이슈로 분류 + 진영(우리유리/상대유리) 판단" },
            { name: "감성강도 부여", desc: "각 클러스터에 -100~+100 감성 점수 (김경수 관점)" },
            { name: "가중점수 산출", desc: "각 클러스터: 기사수 x |감성강도| (최소 10) = 임팩트 점수" },
            { name: "지수화", desc: "우리 점수 / (우리 + 상대) x 100 → 50pt 기준 스케일" },
          ].map((c) => (
            <div key={c.name} className="flex items-center gap-2 py-1 border-b border-[#121e33] last:border-0">
              <span className="text-[10px] text-gray-300 w-28 shrink-0">{c.name}</span>
              <span className="text-[9px] text-gray-500">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">등급 기준</div>
        <div className="flex gap-2 flex-wrap">
          {[
            { g: "우세", t: ">55pt", c: "text-emerald-400" },
            { g: "접전", t: "45~55pt", c: "text-gray-400" },
            { g: "열세", t: "<45pt", c: "text-rose-400" },
          ].map((g) => (
            <span key={g.g} className={`text-[9px] font-bold ${g.c}`}>{g.g} ({g.t})</span>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">현재 값</div>
        <div className="text-[10px] text-gray-400">
          {issue?.index?.toFixed(1) || 50}pt | 우리 {issue?.kim?.mentions||0}건(가중 {issue?.kim?.score||0}) vs 상대 {issue?.park?.mentions||0}건(가중 {issue?.park?.score||0})
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-2">데이터 소스</div>
        <SourceRow name="뉴스 (Naver News API · 광역 11쿼리)" updatedAt={issue?.sources?.news_updated_at} />
        <SourceRow name="AI 클러스터링 (Claude Haiku)" updatedAt={indices?.cluster_updated_at} />
        <div className="mt-2 text-[9px] text-gray-600">업데이트 주기: 1시간 간격 자동 수집 · AI 비용 ~$0.01/회</div>
      </div>
    </div>
  );
}

function ReactionTab({ indices }: { indices: any }) {
  const reaction = indices?.reaction;
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">지표 설명</div>
        <p className="text-[10px] text-gray-400 leading-relaxed">
          뉴스 이슈에 대해 시민들이 실제로 어떻게 반응하는지를 측정하는 실데이터 감성 지표입니다.
          이슈지수에서 추출한 TOP 10 이슈 키워드로 5개 채널을 검색하여 실제 여론 감성을 수집합니다.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">파이프라인</div>
        <div className="space-y-1">
          {[
            { name: "1. 키워드 추출", desc: "이슈지수 AI 클러스터 TOP 10 이슈명을 검색 키워드로 사용" },
            { name: "2. 블로그 수집", desc: "Naver Blog API — 키워드별 최신 30건 제목+감성 분석" },
            { name: "3. 카페 수집", desc: "Naver Cafe API — 키워드별 최신 30건 제목+감성 분석" },
            { name: "4. 유튜브 댓글", desc: "YouTube API — 키워드별 상위 2영상 × 20댓글 감성 분석" },
            { name: "5. 커뮤니티", desc: "디시/에펨/클리앙/더쿠/네이트판/82쿡 + 경남 맘카페 4곳 (10곳)" },
            { name: "6. 뉴스 댓글", desc: "네이버 뉴스 댓글 API — 상위 3기사 × 15댓글 + 공감수" },
          ].map((c) => (
            <div key={c.name} className="flex items-center gap-2 py-1 border-b border-[#121e33] last:border-0">
              <span className="text-[10px] text-gray-300 w-28 shrink-0">{c.name}</span>
              <span className="text-[9px] text-gray-500">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">지수 산출</div>
        <p className="text-[9px] text-gray-400 leading-relaxed">
          각 이슈별 5개 소스 감성 평균 → 우리유리 긍정 vs 상대유리 긍정 비율 → 50pt 기준 스케일.
          &gt;50 = 우리에게 유리한 여론, &lt;50 = 상대에게 유리한 여론. 이슈지수·판세지수와 동일 스케일.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">등급 기준</div>
        <div className="flex gap-2 flex-wrap">
          {[
            { g: "우세", t: ">55pt", c: "text-emerald-400" },
            { g: "접전", t: "45~55pt", c: "text-gray-400" },
            { g: "열세", t: "<45pt", c: "text-rose-400" },
          ].map((g) => (
            <span key={g.g} className={`text-[9px] font-bold ${g.c}`}>{g.g} ({g.t})</span>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">현재 값</div>
        <div className="text-[10px] text-gray-400">
          {reaction?.index?.toFixed(1) || 50}pt | {reaction?.total_mentions?.toLocaleString()||0}건 수집 | {reaction?.keywords_analyzed||0}개 이슈 분석
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-2">데이터 소스 (5개 채널 · 병렬 수집)</div>
        <SourceRow name="블로그 (Naver Blog API)" updatedAt={reaction?.updated_at} />
        <SourceRow name="카페 (Naver Cafe API)" updatedAt={reaction?.updated_at} />
        <SourceRow name="유튜브 댓글 (YouTube Data API)" updatedAt={reaction?.updated_at} />
        <SourceRow name="커뮤니티 (디시/에펨/클리앙/더쿠/네이트판/82쿡)" updatedAt={reaction?.updated_at} />
        <SourceRow name="경남 맘카페 (창원줌마렐라/김해/진주/양산)" updatedAt={reaction?.updated_at} />
        <SourceRow name="뉴스 댓글 (네이버 뉴스 댓글 API)" updatedAt={reaction?.updated_at} />
        <div className="mt-2 text-[9px] text-gray-600">업데이트 주기: 1시간 간격 · 이슈 수집 직후 자동 실행</div>
      </div>
    </div>
  );
}

function PandseTab({ indices }: { indices: any }) {
  const pandse = indices?.pandse;
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">지표 설명</div>
        <p className="text-[10px] text-gray-400 leading-relaxed">
          숨겨진 유권자 이동을 추정하는 종합 판세 지표입니다.
          이슈지수 + 반응지수 + 여론조사 + 국정지지율 + 경제지표를 종합하여
          여론조사에 아직 반영되지 않은 유권자 움직임을 포착합니다. 50pt = 중립.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">구성요소 (9 Factors)</div>
        <div className="space-y-1">
          {[
            { name: "이슈 압력", w: "15%", range: "-50~+50", desc: "이슈지수 연동, 위기 수준별 가중" },
            { name: "이상치 시그널", w: "10%", range: "-50~+50", desc: "비정상 패턴 감지 점수" },
            { name: "반응 모멘텀", w: "15%", range: "-50~+50", desc: "반응지수 연동, 바이럴 방향" },
            { name: "소셜 속도", w: "10%", range: "-50~+50", desc: "구글트렌드 + 감성 모멘텀" },
            { name: "여론조사 관성", w: "20%", range: "-50~+50", desc: "지지율 격차·추세·승률" },
            { name: "이슈지수 직접반영", w: "12%", range: "0~12", desc: "현재 이슈 열기 반영" },
            { name: "반응지수 직접반영", w: "13%", range: "0~13", desc: "현재 참여 수준 반영" },
            { name: "대통령 효과", w: "8%", range: "-5~+8", desc: "국정지지율·여당 지지도 영향" },
            { name: "경제 심리", w: "5%", range: "-3~+3", desc: "소비자심리·물가인식·현직평가" },
          ].map((c) => (
            <div key={c.name} className="flex items-center gap-2 py-1 border-b border-[#121e33] last:border-0">
              <span className="text-[10px] text-gray-300 w-28 shrink-0">{c.name}</span>
              <span className="text-[9px] font-mono text-amber-400 w-8 shrink-0">{c.w}</span>
              <span className="text-[8px] font-mono text-gray-500 w-14 shrink-0">{c.range}</span>
              <span className="text-[9px] text-gray-500">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">Alert 기준</div>
        <p className="text-[9px] text-gray-400">
          이전 대비 <span className="text-amber-400 font-bold">1pt 이상 변동</span> 시 AI 분석 리포트 자동 생성
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-2">데이터 소스</div>
        <SourceRow name="이슈지수 (자체 엔진)" updatedAt={pandse?.sources?.issue_updated_at || indices?.issue?.updated_at} />
        <SourceRow name="반응지수 (자체 엔진)" updatedAt={pandse?.sources?.reaction_updated_at || indices?.reaction?.updated_at} />
        <SourceRow name="여론조사 데이터" updatedAt={pandse?.sources?.poll_updated_at} />
        <SourceRow name="국정지지율 (Gallup 등)" updatedAt={pandse?.sources?.national_poll_updated_at} />
        <SourceRow name="경제지표 (정부 통계)" updatedAt={pandse?.sources?.economic_updated_at} />
        <div className="mt-2 text-[9px] text-gray-600">
          엔진 연산: 1시간 간격 · 여론조사: 발표 시 · 국정지지율: 주 1~2회 · 경제지표: 일/주간
        </div>
      </div>
    </div>
  );
}

export default function SystemPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("이슈지수");
  const indices = useStore((s) => s.indices);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-12" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-[680px] max-h-[80vh] bg-[#080e18] border border-[#1a2844] rounded-xl shadow-2xl overflow-hidden anim-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1a2844]">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-black text-blue-300 uppercase tracking-wider">System</span>
            <span className="text-[9px] text-gray-500">지표 상세 · 데이터 소스 현황</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-[12px] transition-colors">✕</button>
        </div>

        {/* 탭 */}
        <div className="flex border-b border-[#1a2844]">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-[11px] font-bold transition-colors ${
                tab === t
                  ? "text-cyan-300 border-b-2 border-cyan-400 bg-cyan-500/5"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* 본문 */}
        <div className="px-5 py-4 overflow-y-auto max-h-[calc(80vh-100px)]">
          {tab === "이슈지수" && <IssueTab indices={indices} />}
          {tab === "반응지수" && <ReactionTab indices={indices} />}
          {tab === "판세지수" && <PandseTab indices={indices} />}
        </div>
      </div>
    </div>
  );
}
