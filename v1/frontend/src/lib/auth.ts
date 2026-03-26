import { create } from "zustand";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AuthState {
  token: string | null;
  username: string | null;
  tier: number | null;
  label: string | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  checkSession: () => Promise<boolean>;
}

export const useAuth = create<AuthState>((set, get) => ({
  token: typeof window !== "undefined" ? localStorage.getItem("ee_token") : null,
  username: typeof window !== "undefined" ? localStorage.getItem("ee_username") : null,
  tier: typeof window !== "undefined" ? Number(localStorage.getItem("ee_tier") ?? "null") || null : null,
  label: typeof window !== "undefined" ? localStorage.getItem("ee_label") : null,
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        set({ loading: false, error: data.detail || "로그인 실패" });
        return false;
      }
      const data = await res.json();
      localStorage.setItem("ee_token", data.token);
      localStorage.setItem("ee_username", data.username);
      localStorage.setItem("ee_tier", String(data.tier));
      localStorage.setItem("ee_label", data.label);
      set({
        token: data.token,
        username: data.username,
        tier: data.tier,
        label: data.label,
        loading: false,
        error: null,
      });
      return true;
    } catch {
      set({ loading: false, error: "서버 연결 실패" });
      return false;
    }
  },

  logout: () => {
    const token = get().token;
    if (token) {
      fetch(`${API_BASE}/api/auth/logout?token=${token}`, { method: "POST" }).catch(() => {});
    }
    localStorage.removeItem("ee_token");
    localStorage.removeItem("ee_username");
    localStorage.removeItem("ee_tier");
    localStorage.removeItem("ee_label");
    set({ token: null, username: null, tier: null, label: null });
  },

  checkSession: async () => {
    const token = get().token;
    if (!token) return false;
    try {
      const res = await fetch(`${API_BASE}/api/auth/me?token=${token}`);
      if (!res.ok) {
        get().logout();
        return false;
      }
      const data = await res.json();
      set({ username: data.username, tier: data.tier, label: data.label });
      return true;
    } catch {
      // 네트워크 에러 시에도 토큰 클리어 → 로그인 화면으로
      get().logout();
      return false;
    }
  },
}));
