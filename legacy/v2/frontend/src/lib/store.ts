import { create } from "zustand";

type DashboardMode = "monitoring" | "strategy" | "command";

interface AppState {
  activePage: string;
  candidate: string;
  opponent: string;
  selectedKeyword: string;
  dashboardMode: DashboardMode;
  sidebarOpen: boolean;
  setActivePage: (page: string) => void;
  setCandidate: (name: string) => void;
  setOpponent: (name: string) => void;
  setSelectedKeyword: (kw: string) => void;
  setDashboardMode: (mode: DashboardMode) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activePage: "strategy",
  candidate: "",
  opponent: "",
  selectedKeyword: "",
  dashboardMode: "strategy",
  sidebarOpen: false,
  setActivePage: (page) => set({ activePage: page, sidebarOpen: false }),
  setCandidate: (name) => set({ candidate: name }),
  setOpponent: (name) => set({ opponent: name }),
  setSelectedKeyword: (kw) => set({ selectedKeyword: kw }),
  setDashboardMode: (mode) => set({ dashboardMode: mode }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
