"use client";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { fmtTs } from "@/lib/format";
import { ResearchPage } from "./ResearchTab";

const TABS = ["데일리 리포트", "위클리 리포트", "리서치"] as const;
type Tab = (typeof TABS)[number];

function DailyReport() {
  const indices = useStore((s) => s.indices);
  const prediction = useStore((s) => s.prediction);
  const polls = useStore((s) => s.polls);
  const newsClusters = useStore((s) => s.newsClusters);
  const issueRadar = useStore((s) => s.issueRadar);
  const reactionRadar = useStore((s) => s.reactionRadar);
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);

  const { issue, reaction, pandse } = indices || {};
  const poll = prediction?.poll || {};
  const base = prediction?.base || {};
  const dyn = prediction?.dynamic || {};
  const dDay = pandse?.d_day || "?";
  const today = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" });
  const pandseIdx = pandse?.index || 50;
  const pandseDir = pandseIdx > 50 ? "김경수 유리" : pandseIdx < 50 ? "박완수 유리" : "초박빙";

  // 뉴스 전장 통계
  const ourCount = newsClusters.filter((c: any) => c.side?.includes("우리")).length;
  const oppCount = newsClusters.filter((c: any) => c.side?.includes("상대")).length;
  const totalArticles = newsClusters.reduce((sum: number, c: any) => sum + (c.count || 0), 0);

  return (
    <div className="space-y-3">
      {/* 헤더 + 한줄 요약 */}
      <div className="wr-card border-t-2 border-t-blue-600">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[13px] font-bold text-blue-300">전략대응 리포트</h3>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-gray-600">{today}</span>
              <span className="text-[9px] text-amber-400 font-bold">D-{dDay}</span>
              <span className="text-[8px] text-gray-600">{fmtTs(indices?.issue?.updated_at)}</span>
            </div>
          </div>
          <div className="bg-[#080d16] rounded-lg p-3 border border-[#1a2844]">
            <div className="text-[11px] text-gray-200 leading-relaxed">
              여론조사 <span className="text-blue-400 font-bold">{(poll.kim || 0).toFixed(1)}%</span> vs <span className="text-red-400 font-bold">{(poll.park || 0).toFixed(1)}%</span>
              {poll.label ? ` (${poll.label})` : ""}.
              판세지수 <span className={`font-bold ${pandseIdx >= 55 ? "text-emerald-400" : pandseIdx <= 45 ? "text-rose-400" : "text-cyan-400"}`}>{pandseIdx.toFixed(1)}pt</span> ({pandseDir}).
              {" "}뉴스 {totalArticles}건 분석 — 우리 유리 {ourCount}건, 상대 유리 {oppCount}건.
            </div>
          </div>
        </div>
      </div>

      {/* 오늘의 판세 — 컴팩트 테이블 */}
      <div className="wr-card">
        <div className="wr-card-header">오늘의 판세</div>
        <div className="px-4 py-3">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-gray-600 border-b border-[#1a2844]">
                <th className="text-left py-1.5 px-2">항목</th>
                <th className="text-left py-1.5 px-2">현재</th>
                <th className="text-left py-1.5 px-2">해석</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[#0e1825]">
                <td className="py-1.5 px-2 text-gray-300 font-bold">여론조사</td>
                <td className="py-1.5 px-2"><span className="text-blue-400 font-mono">{(poll.kim||0).toFixed(1)}%</span> vs <span className="text-red-400 font-mono">{(poll.park||0).toFixed(1)}%</span></td>
                <td className="py-1.5 px-2 text-gray-400">{(poll.kim||0) > (poll.park||0) ? "우세이나 교차검증 필요" : (poll.kim||0) < (poll.park||0) ? "열세 — 반등 전략 필요" : "초박빙"}</td>
              </tr>
              <tr className="border-b border-[#0e1825]">
                <td className="py-1.5 px-2 text-gray-300 font-bold">실투표 예측</td>
                <td className="py-1.5 px-2"><span className="text-blue-300 font-mono">{(base.kim||50).toFixed(1)}%</span> vs <span className="text-red-300 font-mono">{(base.park||50).toFixed(1)}%</span></td>
                <td className="py-1.5 px-2 text-gray-400">7대 투표율 기반 — 60대 고투표율 반영</td>
              </tr>
              <tr className="border-b border-[#0e1825]">
                <td className="py-1.5 px-2 text-gray-300 font-bold">동향 예측</td>
                <td className="py-1.5 px-2"><span className="text-cyan-300 font-mono">{(dyn.kim||50).toFixed(1)}%</span> vs <span className="text-pink-300 font-mono">{(dyn.park||50).toFixed(1)}%</span></td>
                <td className="py-1.5 px-2 text-gray-400">9 Factors + 선거일 잔여일수 반영</td>
              </tr>
              <tr className="border-b border-[#0e1825]">
                <td className="py-1.5 px-2 text-gray-300 font-bold">판세지수</td>
                <td className="py-1.5 px-2"><span className={`font-mono font-bold ${pandseIdx >= 55 ? "text-emerald-400" : pandseIdx <= 45 ? "text-rose-500" : "text-cyan-400"}`}>{pandseIdx.toFixed(1)}pt</span></td>
                <td className="py-1.5 px-2 text-gray-400">{pandseDir} (50pt = 중립)</td>
              </tr>
              <tr className="border-b border-[#0e1825]">
                <td className="py-1.5 px-2 text-gray-300 font-bold">이슈 노출</td>
                <td className="py-1.5 px-2"><span className="text-blue-400 font-mono">{issue?.kim?.mentions||0}건</span> vs <span className="text-red-400 font-mono">{issue?.park?.mentions||0}건</span></td>
                <td className="py-1.5 px-2 text-gray-400">{(issue?.gap||0) >= 0 ? "노출 우위" : "노출 열세 — 공약 발표로 만회 필요"}</td>
              </tr>
              <tr>
                <td className="py-1.5 px-2 text-gray-300 font-bold">시민 감성</td>
                <td className="py-1.5 px-2"><span className="text-blue-400 font-mono">{reaction?.kim?.pct||0}</span> vs <span className="text-red-400 font-mono">{reaction?.park?.pct||0}</span></td>
                <td className="py-1.5 px-2 text-gray-400">{(reaction?.gap||0) > 0 ? "감성 우위" : (reaction?.gap||0) < 0 ? "감성 열세" : "접전"} ({issue?.kim?.keywords||0}+{issue?.park?.keywords||0}개 채널)</td>
              </tr>
            </tbody>
          </table>
          <div className="mt-2 text-[9px] text-gray-600">
            여론조사상 우세이나, 경남은 보수 텃밭이라 실제 투표에서 60대 이상 높은 투표율로 뒤집힐 수 있음. 3040 세대 투표율 동원이 승패를 결정.
          </div>
        </div>
      </div>

      {/* 뉴스 전장 — TOP 10 클러스터 + 영향도 + 대응 */}
      {newsClusters.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header">
            <span>뉴스 전장</span>
            <span className="text-[8px] text-gray-600 font-normal ml-2 normal-case tracking-normal">{totalArticles}건 수집·분석</span>
          </div>
          <div className="px-4 py-3">
            <div className="text-[8px] text-gray-600 mb-2">점수 기준: +3 매우유리 / +2 유리 / +1 소폭유리 / -1 소폭불리 / -2 불리 / -3 매우불리</div>
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-gray-600 border-b border-[#1a2844]">
                  <th className="text-center py-1.5 w-6">#</th>
                  <th className="text-left py-1.5 px-1">이슈</th>
                  <th className="text-center py-1.5 px-1 w-12">누구측</th>
                  <th className="text-center py-1.5 px-1 w-10">기사</th>
                  <th className="text-center py-1.5 px-1 w-14">우리</th>
                  <th className="text-center py-1.5 px-1 w-14">상대</th>
                </tr>
              </thead>
              <tbody>
                {newsClusters.slice(0, 10).map((c: any, i: number) => {
                  const isOurs = c.side?.includes("우리");
                  const isOpp = c.side?.includes("상대");
                  const ourScore = isOurs ? Math.min(3, Math.max(1, Math.ceil(c.count / 10))) : isOpp ? -Math.min(2, Math.ceil(c.count / 15)) : 0;
                  const oppScore = isOpp ? Math.min(3, Math.max(1, Math.ceil(c.count / 10))) : isOurs ? -Math.min(2, Math.ceil(c.count / 15)) : 0;
                  const sideLabel = isOurs ? "우리 측" : isOpp ? "상대 측" : "중립";
                  const sideColor = isOurs ? "text-blue-400" : isOpp ? "text-red-400" : "text-gray-500";

                  return (
                    <tr key={i}
                      className="border-b border-[#0e1825] cursor-pointer hover:bg-white/[0.02] transition"
                      onClick={() => setExpandedCluster(expandedCluster === i ? null : i)}>
                      <td className="py-1.5 text-center text-gray-400 font-bold">{i + 1}</td>
                      <td className="py-1.5 px-1 text-gray-200">{c.name}</td>
                      <td className={`py-1.5 px-1 text-center text-[9px] ${sideColor}`}>{sideLabel}</td>
                      <td className="py-1.5 px-1 text-center text-gray-400 font-mono">{c.count}</td>
                      <td className={`py-1.5 px-1 text-center font-mono font-bold ${ourScore > 0 ? "text-emerald-400" : ourScore < 0 ? "text-rose-400" : "text-gray-500"}`}>
                        {ourScore > 0 ? `+${ourScore}` : ourScore < 0 ? ourScore : "—"}
                      </td>
                      <td className={`py-1.5 px-1 text-center font-mono font-bold ${oppScore > 0 ? "text-emerald-400" : oppScore < 0 ? "text-rose-400" : "text-gray-500"}`}>
                        {oppScore > 0 ? `+${oppScore}` : oppScore < 0 ? oppScore : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* 확장: 선택한 이슈의 대응 Tip */}
            {expandedCluster !== null && newsClusters[expandedCluster] && (
              <div className="mt-2 bg-cyan-950/10 border border-cyan-800/20 rounded-lg p-3 anim-in">
                <div className="text-[9px] text-cyan-400 font-bold uppercase tracking-widest mb-1">
                  캠프 대응 Tip — {newsClusters[expandedCluster].name}
                </div>
                <div className="text-[10px] text-gray-300 leading-relaxed">
                  {newsClusters[expandedCluster].tip || "AI 분석 대기 중..."}
                </div>
                {newsClusters[expandedCluster].articles?.length > 0 && (
                  <div className="mt-1.5 space-y-0.5">
                    {newsClusters[expandedCluster].articles.slice(0, 3).map((a: any, j: number) => (
                      <div key={j} className="text-[8px] text-gray-500">▸ {a.title}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mt-2 text-[9px] text-gray-600">
              해석 원칙: 현직 도지사(박완수)의 정책 발표·성과는 기본적으로 상대에게 유리로 판정.
              현직은 예산·행정력·미디어 접근성에서 구조적 우위.
            </div>
          </div>
        </div>
      )}

      {/* 시민 반응 vs 뉴스 괴리 분석 */}
      {issueRadar.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header">시민이 관심 있는 이슈 — 뉴스 vs 반응 비교</div>
          <div className="px-4 py-3">
            <div className="text-[9px] text-gray-500 mb-2">뉴스가 많이 나오는 이슈와 시민이 실제로 반응하는 이슈는 다릅니다.</div>
            <div className="space-y-1">
              {issueRadar.slice(0, 5).map((item: any, i: number) => {
                const newsBar = Math.min(100, (item.news_count || item.count || 0) / 2);
                const reactionBar = Math.min(100, (item.reaction_score || item.score || 0));
                return (
                  <div key={i} className="py-1.5 border-b border-[#0e1825] last:border-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-gray-200 font-bold">{item.keyword || item.name}</span>
                      <span className={`text-[8px] ${item.side === "우리" ? "text-blue-400" : item.side === "상대" ? "text-red-400" : "text-gray-500"}`}>{item.side || ""}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 w-10 shrink-0">뉴스</span>
                      <div className="flex-1 h-1.5 bg-[#0a1020] rounded overflow-hidden">
                        <div className="h-full bg-blue-500/50 rounded" style={{ width: `${newsBar}%` }} />
                      </div>
                      <span className="text-[8px] text-gray-500 w-10 shrink-0">반응</span>
                      <div className="flex-1 h-1.5 bg-[#0a1020] rounded overflow-hidden">
                        <div className="h-full bg-amber-500/50 rounded" style={{ width: `${reactionBar}%` }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-2 text-[9px] text-amber-400/80">
              시민 반응이 높은 이슈 = 공약 투입 시 자연 확산 효과 최대. 뉴스만 있고 반응 없는 이슈는 아직 도민이 체감 전.
            </div>
          </div>
        </div>
      )}

      {/* 판세 Alert */}
      {indices?.pandse_alert && (
        <div className="wr-card border-l-2 border-l-amber-500">
          <div className="px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9px] text-amber-400 font-bold">판세 변동 감지</span>
              <span className={`text-[10px] font-mono font-bold ${indices.pandse_alert.direction === "up" ? "text-emerald-400" : "text-rose-400"}`}>
                {indices.pandse_alert.delta > 0 ? "+" : ""}{indices.pandse_alert.delta?.toFixed(1)}pt
              </span>
            </div>
            <div className="text-[10px] text-gray-300 leading-relaxed">{indices.pandse_alert.memo}</div>
          </div>
        </div>
      )}

      {/* 주의사항 */}
      <div className="wr-card border-t-2 border-t-red-900/50">
        <div className="px-4 py-3 space-y-2">
          <div className="text-[10px] text-red-400 font-bold">주의사항</div>
          <div className="space-y-1.5 text-[9px] text-gray-400">
            <div className="flex gap-2">
              <span className="text-red-400 shrink-0">&#x26D4;</span>
              <span>상대 현직 성과(지원금·산단 등)에 대한 직접 부정·비하 금지. "더 잘할 수 있다"의 확장 프레임으로만 대응.</span>
            </div>
            <div className="flex gap-2">
              <span className="text-red-400 shrink-0">&#x26D4;</span>
              <span>중앙당 내홍·이재명 이슈 과도 편승 금지. "경남만 보고 간다" 원칙 고수. 중앙 질문에 짧게 답하고 즉시 지역 의제로 전환.</span>
            </div>
            <div className="flex gap-2">
              <span className="text-amber-400 shrink-0">&#x26A0;</span>
              <span>투표율 구조: 60대 이상 고투표율로 구조적 불리. 3040 사전투표 동원 캠페인 병행 필수.</span>
            </div>
          </div>
        </div>
      </div>

      {/* 데이터 출처 */}
      <div className="text-[8px] text-gray-700 space-y-0.5 px-1">
        <div>뉴스 클러스터: 네이버 뉴스 API, 11개 검색어, 24시간 내 수집·분석</div>
        <div>진영 영향도: AI 분석 (Claude) — 클러스터별 우리/상대 영향 점수 산출</div>
        <div>시민 반응도: 블로그·카페·유튜브·커뮤니티 4개 채널 종합</div>
        <div>감성분석: AI 6분류 (지지/스윙/중립/부정/정체성/정책)</div>
      </div>
    </div>
  );
}

function WeeklyReport() {
  const indices = useStore((s) => s.indices);
  const history = useStore((s) => s.history);
  const candidateTrend = useStore((s) => s.candidateTrend);
  const pandse = indices?.pandse;

  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - weekStart.getDay());
  const weekLabel = weekStart.toLocaleDateString("ko-KR", { month: "2-digit", day: "2-digit" }) + " 주간";

  // 주간 트렌드 요약 (최근 7개 데이터 포인트)
  const recentTrend = candidateTrend.slice(-7);
  const trendStart = recentTrend[0];
  const trendEnd = recentTrend[recentTrend.length - 1];

  return (
    <div className="space-y-3">
      <div className="wr-card border-t-2 border-t-amber-600">
        <div className="px-4 py-3">
          <h3 className="text-[13px] font-bold text-amber-300">Weekly Report — {weekLabel}</h3>
          <p className="text-[10px] text-gray-500 mt-1">주간 지표 변동 추이 및 판세 분석</p>
        </div>
      </div>

      {/* 판세지수 주간 변동 */}
      <div className="wr-card">
        <div className="wr-card-header">판세지수 주간 추이</div>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className={`text-[28px] font-black wr-metric ${(pandse?.index || 50) >= 55 ? "text-emerald-400" : (pandse?.index || 50) <= 45 ? "text-rose-500" : "text-cyan-400"}`}>
                {(pandse?.index || 50).toFixed(1)}<span className="text-[9px] text-gray-500 ml-0.5">pt</span>
              </div>
              <div className="text-[9px] text-gray-500">현재 판세지수</div>
            </div>
            {trendStart && trendEnd && (
              <div className="text-right">
                <div className={`text-[14px] font-black wr-metric ${(trendEnd.pandse - trendStart.pandse) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {(trendEnd.pandse - trendStart.pandse) >= 0 ? "+" : ""}{(trendEnd.pandse - trendStart.pandse).toFixed(1)}pt
                </div>
                <div className="text-[9px] text-gray-500">주간 변동</div>
              </div>
            )}
          </div>
          {indices?.pandse_alert && (
            <div className="bg-amber-950/20 border border-amber-700/40 rounded-lg px-3 py-2">
              <div className="text-[9px] text-amber-400 font-bold mb-0.5">판세 변동 Alert</div>
              <div className="text-[10px] text-amber-300/80">{indices.pandse_alert.memo}</div>
            </div>
          )}
        </div>
      </div>

      {/* 후보별 주간 변동 */}
      {trendStart && trendEnd && (
        <div className="wr-card">
          <div className="wr-card-header">후보별 주간 지표 변동</div>
          <div className="px-4 py-3">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-gray-600 border-b border-[#1a2844]">
                  <th className="text-left py-1.5 px-2">지표</th>
                  <th className="text-center py-1.5 px-2 text-blue-400">김경수 (시작)</th>
                  <th className="text-center py-1.5 px-2 text-blue-400">김경수 (현재)</th>
                  <th className="text-center py-1.5 px-2">변동</th>
                  <th className="text-center py-1.5 px-2 text-red-400">박완수 (시작)</th>
                  <th className="text-center py-1.5 px-2 text-red-400">박완수 (현재)</th>
                  <th className="text-center py-1.5 px-2">변동</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "이슈 언급량", kS: trendStart.issue_kim, kE: trendEnd.issue_kim, pS: trendStart.issue_park, pE: trendEnd.issue_park },
                  { label: "반응 감성", kS: trendStart.reaction_kim, kE: trendEnd.reaction_kim, pS: trendStart.reaction_park, pE: trendEnd.reaction_park },
                ].map((row) => (
                  <tr key={row.label} className="border-b border-[#0e1825]">
                    <td className="py-1.5 px-2 text-gray-300 font-bold">{row.label}</td>
                    <td className="py-1.5 px-2 text-center text-gray-400 font-mono">{row.kS}</td>
                    <td className="py-1.5 px-2 text-center text-blue-400 font-mono font-bold">{row.kE}</td>
                    <td className={`py-1.5 px-2 text-center font-mono font-bold ${(row.kE - row.kS) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(row.kE - row.kS) >= 0 ? "+" : ""}{row.kE - row.kS}
                    </td>
                    <td className="py-1.5 px-2 text-center text-gray-400 font-mono">{row.pS}</td>
                    <td className="py-1.5 px-2 text-center text-red-400 font-mono font-bold">{row.pE}</td>
                    <td className={`py-1.5 px-2 text-center font-mono font-bold ${(row.pE - row.pS) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(row.pE - row.pS) >= 0 ? "+" : ""}{row.pE - row.pS}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 일별 데이터 포인트 */}
      {recentTrend.length > 0 && (
        <div className="wr-card">
          <div className="wr-card-header">주간 데이터 타임라인</div>
          <div className="px-4 py-3 space-y-1">
            {recentTrend.map((d: any, i: number) => (
              <div key={i} className="flex items-center gap-3 py-1 border-b border-[#0e1825] last:border-0 text-[9px]">
                <span className="text-gray-500 w-20 font-mono">{d.date}</span>
                <span className="text-blue-400 w-16">이슈 {d.issue_kim}</span>
                <span className="text-red-400 w-16">이슈 {d.issue_park}</span>
                <span className="text-blue-400 w-16">반응 {d.reaction_kim}</span>
                <span className="text-red-400 w-16">반응 {d.reaction_park}</span>
                <span className="text-cyan-400 font-bold">판세 {d.pandse?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("데일리 리포트");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-6" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-[900px] max-h-[90vh] bg-[#080e18] border border-[#1a2844] rounded-xl shadow-2xl overflow-hidden anim-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1a2844]">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-black text-blue-300 uppercase tracking-wider">Report</span>
            <span className="text-[9px] text-gray-500">전략 리포트 · 리서치</span>
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
        <div className="px-5 py-4 overflow-y-auto max-h-[calc(90vh-100px)]">
          {tab === "데일리 리포트" && <DailyReport />}
          {tab === "위클리 리포트" && <WeeklyReport />}
          {tab === "리서치" && <ResearchPage />}
        </div>
      </div>
    </div>
  );
}
