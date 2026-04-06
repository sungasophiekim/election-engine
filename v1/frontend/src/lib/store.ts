import { create } from "zustand";
import * as api from "./api";

interface WarRoomState {
  polls: any[];
  nationalTrend: any[];
  prediction: any;
  indices: any;
  history: any[];
  candidateTrend: any[];
  newsClusters: any[];
  reactionRadar: any[];
  collectionStatus: any;
  loading: boolean;
  lastUpdated: string;
  newPollAlert: { label: string; date: string } | null;
  dismissAlert: () => void;
  fetchAll: () => Promise<void>;
}

export const useStore = create<WarRoomState>((set) => ({
  polls: [],
  nationalTrend: [],
  prediction: null,
  indices: null,
  history: [],
  candidateTrend: [],
  newsClusters: [],
  reactionRadar: [],
  collectionStatus: null,
  loading: true,
  lastUpdated: "",
  newPollAlert: null,
  dismissAlert: () => set({ newPollAlert: null }),
  fetchAll: async () => {
    const prevPolls = useStore.getState().polls;
    set({ loading: true });
    const [polls, prediction, indices, hist, clusters, reaction, colStatus] = await Promise.all([
      api.getPolls().catch(() => ({ polls: [] })),
      api.getPrediction().catch(() => null),
      api.getIndicesCurrent().catch(() => null),
      api.getIndicesHistory().catch(() => ({ trend: [] })),
      api.getNewsClusters().catch(() => ({ clusters: [] })),
      api.getReactionRadar().catch(() => ({ items: [] })),
      api.getCollectionStatus().catch(() => null),
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
      nationalTrend: polls?.national_trend || [],
      prediction,
      indices,
      history: hist?.trend || [],
      candidateTrend: hist?.candidate_trend || [],
      newsClusters: clusters?.clusters || [],
      reactionRadar: reaction?.items || [],
      collectionStatus: colStatus,
      loading: false,
      newPollAlert,
      lastUpdated: indices?.server_updated_at || new Date().toISOString(),
    });
  },
}));
