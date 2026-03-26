"use client";
import { Sidebar } from "@/components/Sidebar";
import { CommandStrip } from "@/components/CommandStrip";
import { WarRoom } from "@/components/WarRoom";
import { IssuesPage } from "@/components/IssuesPage";
import { SocialPage } from "@/components/SocialPage";
import { PollingPage } from "@/components/PollingPage";
import { StrategyPage } from "@/components/StrategyPage";
import { DebatePage } from "@/components/DebatePage";
import { RegionsPage } from "@/components/RegionsPage";
import { LearningPage } from "@/components/LearningPage";
import { ResearchPage } from "@/components/ResearchPage";
import { IndicesPage } from "@/components/IndicesPage";
import { OpponentPage } from "@/components/OpponentPage";
import { ReportPage } from "@/components/ReportPage";
import { SystemPage } from "@/components/SystemPage";
import { KeywordMonitorPage } from "@/components/KeywordMonitorPage";
import { MobileApp } from "@/components/mobile/MobileApp";
import { useAppStore } from "@/lib/store";
import { useIsMobile } from "@/lib/useIsMobile";

const PAGES: Record<string, React.ComponentType> = {
  warroom: WarRoom,
  strategy: StrategyPage,
  report: ReportPage,
  debate: DebatePage,
  regions: RegionsPage,
  polling: PollingPage,
  issues: IssuesPage,
  opponent: OpponentPage,
  indices: IndicesPage,
  research: ResearchPage,
  learning: LearningPage,
  keywords: KeywordMonitorPage,
  system: SystemPage,
};

export default function Home() {
  const activePage = useAppStore((s) => s.activePage);
  const isMobile = useIsMobile();
  const Page = PAGES[activePage] || WarRoom;

  if (isMobile) {
    return <MobileApp />;
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <CommandStrip />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-2">
          <Page />
        </main>
      </div>
    </div>
  );
}
