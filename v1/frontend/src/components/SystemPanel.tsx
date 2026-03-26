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
          이슈가 얼마나 &quot;터졌는가&quot;를 측정하는 순수 규모·속도 지표입니다.
          감성(긍정/부정)이 아닌, 이슈의 확산 규모와 속도만을 측정합니다.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">구성요소 (100점 만점)</div>
        <div className="space-y-1">
          {[
            { name: "뉴스 볼륨", pts: 25, desc: "Naver News API 기반 중복제거 기사 수" },
            { name: "미디어 티어", pts: 20, desc: "TV·포털·1티어 매체 비중 분류" },
            { name: "확산 속도", pts: 30, desc: "6h/18h 속도비 + 이상치 + 전일비" },
            { name: "후보 연결도", pts: 15, desc: "직접언급·정책·지역 연관도" },
            { name: "채널 다양성", pts: 10, desc: "5개+ 채널 동시 감지 시 만점" },
          ].map((c) => (
            <div key={c.name} className="flex items-center gap-2 py-1 border-b border-[#121e33] last:border-0">
              <span className="text-[10px] text-gray-300 w-20 shrink-0">{c.name}</span>
              <span className="text-[9px] font-mono text-cyan-400 w-8 shrink-0">{c.pts}점</span>
              <span className="text-[9px] text-gray-500">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">등급 기준</div>
        <div className="flex gap-2 flex-wrap">
          {[
            { g: "EXPLOSIVE", t: "≥80", c: "text-red-400" },
            { g: "HOT", t: "≥60", c: "text-orange-400" },
            { g: "ACTIVE", t: "≥40", c: "text-yellow-400" },
            { g: "LOW", t: "≥20", c: "text-gray-400" },
            { g: "DORMANT", t: "<20", c: "text-gray-600" },
          ].map((g) => (
            <span key={g.g} className={`text-[9px] font-bold ${g.c}`}>{g.g}({g.t})</span>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-2">데이터 소스 (7개 채널)</div>
        <SourceRow name="뉴스 (Naver News API)" updatedAt={issue?.sources?.news_updated_at} />
        <SourceRow name="블로그 (Naver Blog)" updatedAt={issue?.sources?.blog_updated_at} />
        <SourceRow name="카페 (Naver Cafe)" updatedAt={issue?.sources?.cafe_updated_at} />
        <SourceRow name="유튜브 (YouTube API)" updatedAt={issue?.sources?.youtube_updated_at} />
        <SourceRow name="구글트렌드 (Google Trends)" updatedAt={issue?.sources?.trends_updated_at} />
        <SourceRow name="커뮤니티 (19+곳)" updatedAt={issue?.sources?.community_updated_at} />
        <SourceRow name="네이버 데이터랩" updatedAt={issue?.sources?.datalab_updated_at} />
        <div className="mt-2 text-[9px] text-gray-600">업데이트 주기: 10분 간격 자동 수집</div>
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
          사람들이 &quot;어떻게 반응하는가&quot;를 측정하는 감성·참여·바이럴 지표입니다.
          커뮤니티 공명, 콘텐츠 생성량, 감성 방향, 검색 반응, 유튜브 인게이지먼트를 종합 분석합니다.
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">구성요소 (100점 만점)</div>
        <div className="space-y-1">
          {[
            { name: "커뮤니티 공명", pts: 25, desc: "19+ 커뮤니티 바이럴 패턴 감지" },
            { name: "콘텐츠 생성", pts: 20, desc: "블로그·카페·유튜브 게시량 추적" },
            { name: "감성 방향", pts: 20, desc: "뉴스(35%)+블로그(25%)+카페(20%)+유튜브(15%)+댓글(25%)" },
            { name: "검색 반응", pts: 15, desc: "구글트렌드 관심도·7일변화·급등감지" },
            { name: "유튜브 인게이지먼트", pts: 20, desc: "댓글수·좋아요·조회수·댓글감성" },
          ].map((c) => (
            <div key={c.name} className="flex items-center gap-2 py-1 border-b border-[#121e33] last:border-0">
              <span className="text-[10px] text-gray-300 w-28 shrink-0">{c.name}</span>
              <span className="text-[9px] font-mono text-cyan-400 w-8 shrink-0">{c.pts}점</span>
              <span className="text-[9px] text-gray-500">{c.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">속도 보너스</div>
        <p className="text-[9px] text-gray-400">
          이상치+서프라이즈 ≥80 → <span className="text-amber-400">x1.15</span> · 이상치 or 서프라이즈 ≥60 → <span className="text-amber-400">x1.10</span>
        </p>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-1">등급 기준</div>
        <div className="flex gap-2 flex-wrap">
          {[
            { g: "VIRAL", t: "≥75", c: "text-red-400" },
            { g: "ENGAGED", t: "≥50", c: "text-orange-400" },
            { g: "RIPPLE", t: "≥25", c: "text-yellow-400" },
            { g: "SILENT", t: "<25", c: "text-gray-600" },
          ].map((g) => (
            <span key={g.g} className={`text-[9px] font-bold ${g.c}`}>{g.g}({g.t})</span>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] text-cyan-300 font-bold mb-2">데이터 소스 (6개 레이어)</div>
        <SourceRow name="커뮤니티 (19+곳)" updatedAt={reaction?.sources?.community_updated_at} />
        <SourceRow name="블로그 / 카페" updatedAt={reaction?.sources?.social_updated_at} />
        <SourceRow name="유튜브 (YouTube API)" updatedAt={reaction?.sources?.youtube_updated_at} />
        <SourceRow name="뉴스 댓글" updatedAt={reaction?.sources?.comments_updated_at} />
        <SourceRow name="구글트렌드" updatedAt={reaction?.sources?.trends_updated_at} />
        <SourceRow name="감성 분석 (Claude AI)" updatedAt={reaction?.sources?.sentiment_updated_at} />
        <div className="mt-2 text-[9px] text-gray-600">업데이트 주기: 10분 간격 자동 수집</div>
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
          엔진 연산: 10분 간격 · 여론조사: 발표 시 · 국정지지율: 주 1~2회 · 경제지표: 일/주간
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
