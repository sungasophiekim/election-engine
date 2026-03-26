"use client";
import { useEffect, useState } from "react";
import { getSocialBuzz, getCommunity, getSnsBattle } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function SocialPage() {
  const [buzz, setBuzz] = useState<any>(null);
  const [community, setCommunity] = useState<any>(null);
  const [snsBattle, setSnsBattle] = useState<any>(null);
  const candidate = useAppStore((s) => s.candidate) || "김경수";
  const opponent = useAppStore((s) => s.opponent) || "박완수";

  useEffect(() => {
    getSocialBuzz().then(setBuzz).catch(() => {});
    getCommunity().then(setCommunity).catch(() => {});
    getSnsBattle().then(setSnsBattle).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      {/* 소셜 버즈 비교 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {buzz?.candidates && Object.entries(buzz.candidates).map(([name, c]: [string, any]) => {
          const isOur = name === candidate;
          const total = c.social_total || c.total_buzz || 0;
          return (
            <div key={name} className={`bg-bg-card border rounded-lg p-4 ${isOur ? "border-blue-800" : "border-red-800"}`}>
              <h3 className={`font-bold text-lg mb-3 ${isOur ? "text-blue-400" : "text-red-400"}`}>{name}</h3>
              <div className="text-3xl font-bold text-white mb-3">{total?.toLocaleString()}<span className="text-sm text-gray-500 ml-1">건</span></div>
              <div className="space-y-2 text-sm">
                <ChannelBar label="📝 블로그" value={c.blog || 0} max={total || 1} color={isOur ? "#1976d2" : "#c62828"} />
                <ChannelBar label="💬 카페" value={c.cafe || 0} max={total || 1} color={isOur ? "#1565c0" : "#b71c1c"} />
                {(c.youtube_count || 0) > 0 && <div className="text-gray-400">▶ 유튜브: {c.youtube_count}건 ({c.youtube_views?.toLocaleString()}조회)</div>}
                {(c.trend_interest || 0) > 0 && (
                  <div className="text-gray-400">
                    📊 구글트렌드: {c.trend_interest}/100
                    <span className={(c.trend_change || 0) > 0 ? "text-red-400 ml-1" : "text-green-400 ml-1"}>
                      {(c.trend_change || 0) > 0 ? "+" : ""}{c.trend_change?.toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              <div className="mt-3 pt-2 border-t border-border">
                <span className="text-xs text-gray-500">감성: </span>
                <span className={`font-bold ${(c.sentiment || 0) > 0 ? "text-green-400" : (c.sentiment || 0) < 0 ? "text-red-400" : "text-orange-400"}`}>
                  {(c.sentiment || 0).toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 요약 통계 */}
      {buzz?.summary && (
        <div className="bg-bg-card border border-border rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3">요약 통계</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-sm">
            <div>
              <div className="text-gray-500">버즈 비율</div>
              <div className="text-white font-bold text-lg">{buzz.summary.buzz_ratio?.toFixed(1)}배</div>
            </div>
            <div>
              <div className="text-gray-500">감성 우위</div>
              <div className={`font-bold text-lg ${(buzz.summary.sentiment_advantage || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {(buzz.summary.sentiment_advantage || 0) >= 0 ? "+" : ""}{buzz.summary.sentiment_advantage?.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-gray-500">버즈 리더</div>
              <div className="text-white font-bold">{buzz.summary.buzz_leader || "-"}</div>
            </div>
            <div>
              <div className="text-gray-500">감성 리더</div>
              <div className="text-white font-bold">{buzz.summary.sentiment_leader || "-"}</div>
            </div>
          </div>
        </div>
      )}

      {/* 커뮤니티 여론 */}
      {community && (
        <div className="bg-bg-card border border-orange-800 rounded-lg p-4">
          <h3 className="text-orange-400 text-sm font-semibold mb-3">🏛 커뮤니티 여론</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {(community.communities || []).map((c: any, i: number) => (
              <div key={i} className="bg-[#0d1117] rounded p-3 text-center">
                <div className="text-white font-bold text-sm">{c.name}</div>
                <div className="text-gray-400 text-xs mt-1">{c.mentions}건</div>
                <div className="flex justify-center gap-2 mt-2 text-xs">
                  <span className="text-green-400">👍 {c.positive || 0}</span>
                  <span className="text-red-400">👎 {c.negative || 0}</span>
                </div>
              </div>
            ))}
          </div>
          {community.overall_tone && (
            <div className="mt-3 text-sm text-gray-400">전체 톤: <strong className="text-white">{community.overall_tone}</strong></div>
          )}
        </div>
      )}

      {/* SNS 채널 비교 */}
      {snsBattle?.candidates && (
        <div className="bg-bg-card border border-blue-800 rounded-lg p-4">
          <h3 className="text-blue-400 text-sm font-semibold mb-3">📱 SNS 채널 비교</h3>

          {/* Summary battle bars */}
          {snsBattle.summary && (
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <div className="text-gray-500 text-xs">게시물</div>
                <div className="text-2xl font-bold">
                  <span className="text-blue-400">{snsBattle.summary.our_posts}</span>
                  <span className="text-gray-600 text-sm mx-1">vs</span>
                  <span className="text-red-400">{snsBattle.summary.opp_posts}</span>
                </div>
                <div className={`text-xs font-bold ${snsBattle.summary.post_ratio >= 1 ? "text-blue-400" : "text-red-400"}`}>
                  {snsBattle.summary.post_ratio >= 1 ? "우세" : "열세"} ({snsBattle.summary.post_ratio}x)
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-500 text-xs">참여도</div>
                <div className="text-2xl font-bold">
                  <span className="text-blue-400">{snsBattle.summary.our_engagement?.toLocaleString()}</span>
                  <span className="text-gray-600 text-sm mx-1">vs</span>
                  <span className="text-red-400">{snsBattle.summary.opp_engagement?.toLocaleString()}</span>
                </div>
                <div className={`text-xs font-bold ${snsBattle.summary.engagement_ratio >= 1 ? "text-blue-400" : "text-red-400"}`}>
                  {snsBattle.summary.engagement_ratio >= 1 ? "우세" : "열세"} ({snsBattle.summary.engagement_ratio}x)
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-500 text-xs">팔로워</div>
                <div className="text-2xl font-bold">
                  <span className="text-blue-400">{snsBattle.summary.our_followers?.toLocaleString()}</span>
                  <span className="text-gray-600 text-sm mx-1">vs</span>
                  <span className="text-red-400">{snsBattle.summary.opp_followers?.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}

          {/* Per-candidate channel detail */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(snsBattle.candidates).map(([name, data]: [string, any]) => {
              const isOur = name === candidate;
              return (
                <div key={name} className={`rounded-lg p-3 border ${isOur ? "border-blue-800/50 bg-blue-950/10" : "border-red-800/50 bg-red-950/10"}`}>
                  <div className={`font-bold text-sm mb-2 ${isOur ? "text-blue-400" : "text-red-400"}`}>{name}</div>
                  <div className="space-y-2">
                    {(data.channels || []).map((ch: any) => (
                      <div key={ch.channel} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-500">
                            {ch.channel === "facebook" ? "📘" : ch.channel === "youtube" ? "▶️" : ch.channel === "instagram" ? "📷" : "🌐"}
                          </span>
                          <span className="text-gray-300 capitalize">{ch.channel}</span>
                          <span className={`text-[9px] px-1.5 rounded ${
                            ch.status === "connected" ? "bg-emerald-950/40 text-emerald-400" :
                            ch.status === "manual" ? "bg-yellow-950/40 text-yellow-400" :
                            "bg-gray-800/40 text-gray-500"
                          }`}>{ch.status}</span>
                        </div>
                        <div className="flex items-center gap-3 text-gray-400">
                          <span>{ch.recent_posts}건</span>
                          <span>{ch.engagement?.toLocaleString() || 0} 참여</span>
                          {ch.followers > 0 && <span>{ch.followers?.toLocaleString()} 팔로워</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Top content */}
                  {data.channels?.some((c: any) => c.top_content?.length > 0) && (
                    <div className="mt-2 pt-2 border-t border-gray-800">
                      <div className="text-[10px] text-gray-600 mb-1">최근 콘텐츠</div>
                      {data.channels.flatMap((c: any) => (c.top_content || []).map((t: any) => ({ ...t, ch: c.channel }))).slice(0, 3).map((t: any, i: number) => (
                        <div key={i} className="text-[10px] text-gray-400 truncate py-0.5">
                          {t.ch === "facebook" ? "📘" : t.ch === "youtube" ? "▶️" : "📷"} {t.title}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Config info */}
          {snsBattle.sns_config && (
            <div className="mt-3 pt-3 border-t border-gray-800 text-[10px] text-gray-600">
              설정된 계정: {Object.entries(snsBattle.sns_config.candidate_sns || {}).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`).join(" · ") || "없음"}
            </div>
          )}
        </div>
      )}

      {!buzz && !community && !snsBattle && <div className="text-center py-8 text-gray-500">로딩...</div>}
    </div>
  );
}

function ChannelBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-gray-400">{label}</span>
      <div className="flex-1 h-3 bg-border rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
      <span className="w-12 text-right text-gray-300">{value}</span>
    </div>
  );
}
