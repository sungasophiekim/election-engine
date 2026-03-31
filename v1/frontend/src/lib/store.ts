import { create } from "zustand";
import * as api from "./api";

interface WarRoomState {
  polls: any[];
  prediction: any;
  indices: any;
  history: any[];
  candidateTrend: any[];
  newsClusters: any[];
  issueRadar: any[];
  reactionRadar: any[];
  loading: boolean;
  lastUpdated: string;
  newPollAlert: { label: string; date: string } | null;
  dismissAlert: () => void;
  fetchAll: () => Promise<void>;
}

export const useStore = create<WarRoomState>((set) => ({
  polls: [],
  prediction: null,
  indices: null,
  history: [],
  candidateTrend: [],
  newsClusters: [],
  issueRadar: [],
  reactionRadar: [],
  loading: true,
  lastUpdated: "",
  newPollAlert: null,
  dismissAlert: () => set({ newPollAlert: null }),
  fetchAll: async () => {
    const prevPolls = useStore.getState().polls;
    set({ loading: true });
    const [polls, prediction, indices, hist, clusters, issue, reaction] = await Promise.all([
      api.getPolls().catch(() => ({ polls: [] })),
      api.getPrediction().catch(() => null),
      api.getIndicesCurrent().catch(() => null),
      api.getIndicesHistory().catch(() => ({ trend: [] })),
      api.getNewsClusters().catch(() => ({ clusters: [] })),
      api.getIssueRadar().catch(() => ({ items: [] })),
      api.getReactionRadar().catch(() => ({ items: [] })),
    ]);
    const newPolls = polls?.polls || [];
    // 새 여론조사 감지: 이전 데이터가 있고 최신 poll이 변경된 경우
    let newPollAlert = useStore.getState().newPollAlert;
    if (prevPolls.length > 0 && newPolls.length > 0) {
      const prevLatest = prevPolls[prevPolls.length - 1];
      const curLatest = newPolls[newPolls.length - 1];
      if (curLatest.date !== prevLatest.date || curLatest.label !== prevLatest.label) {
        newPollAlert = { label: curLatest.label, date: curLatest.date };
      }
    }
    set({
      polls: newPolls,
      prediction,
      indices,
      history: hist?.trend || [],
      candidateTrend: hist?.candidate_trend || [],
      newsClusters: clusters?.clusters || [],
      issueRadar: issue?.items || [],
      reactionRadar: reaction?.items || [],
      loading: false,
      newPollAlert,
      lastUpdated: indices?.server_updated_at || new Date().toISOString(),
    });
  },
}));
