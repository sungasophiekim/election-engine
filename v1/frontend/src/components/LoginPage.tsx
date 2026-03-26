"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, loading, error } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(username, password);
  };

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-[360px] anim-in">
        <div className="text-center mb-8">
          <div className="text-[11px] text-cyan-400/60 font-mono uppercase tracking-[0.3em] mb-2">
            Election Engine v1
          </div>
          <h1 className="text-[20px] font-black text-blue-300 uppercase tracking-wider">
            War Room
          </h1>
          <div className="text-[10px] text-gray-600 mt-1">경남도지사 선거 전략 대시보드</div>
        </div>

        <form onSubmit={handleSubmit} className="wr-card border-pulse p-6 space-y-4">
          <div>
            <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block mb-1.5">
              ID
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-[#060c16] border border-[#1a2844] rounded-lg px-3 py-2.5 text-[12px] text-gray-200 focus:outline-none focus:border-cyan-700 transition-colors placeholder-gray-700"
              placeholder="아이디를 입력하세요"
              autoFocus
            />
          </div>
          <div>
            <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#060c16] border border-[#1a2844] rounded-lg px-3 py-2.5 text-[12px] text-gray-200 focus:outline-none focus:border-cyan-700 transition-colors placeholder-gray-700"
              placeholder="비밀번호를 입력하세요"
            />
          </div>

          {error && (
            <div className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full py-2.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all disabled:opacity-30 disabled:cursor-not-allowed bg-cyan-900/40 border border-cyan-700/40 text-cyan-300 hover:bg-cyan-800/40 hover:border-cyan-600/50"
          >
            {loading ? "인증 중..." : "로그인"}
          </button>
        </form>

        <div className="text-center mt-4 text-[8px] text-gray-700">
          Authorized access only
        </div>
      </div>
    </div>
  );
}
