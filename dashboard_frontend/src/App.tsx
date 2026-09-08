import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPositions, fetchSystemStatus } from "@/lib/api";
import { Sidebar, NavSection } from "./components/layout/Sidebar";
import { TopNav } from "./components/layout/TopNav";
import { OverviewSection } from "./features/overview/OverviewSection";
import { ChartPanel } from "./features/chart/ChartPanel";
import { PositionsPanel } from "./features/positions/PositionsPanel";
import { AnalyticsPanel } from "./features/analytics/AnalyticsPanel";
import { JournalTable } from "./features/journal/JournalTable";
import { RiskConfigPanel } from "./features/risk-config/RiskConfigPanel";
import { LiveLogFeed } from "./features/live-log/LiveLogFeed";
import { Toaster } from "sonner";

function App() {
  const [currentSection, setCurrentSection] = useState<NavSection>("overview");
  const [collapsed, setCollapsed] = useState(false);

  const { data: positions = [] } = useQuery({
    queryKey: ["positions"],
    queryFn: fetchPositions,
    refetchInterval: 2000,
  });

  const { data: status = { botStatus: "running", mt5Connected: false, regime: "ranging" } } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: fetchSystemStatus,
    refetchInterval: 3000,
  });

  return (
    <div className="h-screen w-screen overflow-hidden bg-background text-foreground dark flex">
      {/* Navigation Sidebar */}
      <Sidebar
        currentSection={currentSection}
        onSelectSection={setCurrentSection}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        activePositionsCount={positions.length}
        mt5Connected={status.mt5Connected}
        botStatus={status.botStatus}
      />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <TopNav
          currentSection={currentSection}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed(!collapsed)}
        />

        {/* Scrollable Section Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-gradient-to-b from-background via-background/95 to-black/60">
          <div className="max-w-7xl mx-auto space-y-6">
            {currentSection === "overview" && (
              <OverviewSection onNavigate={setCurrentSection} />
            )}

            {currentSection === "chart" && (
              <div className="flex flex-col gap-4">
                <div className="h-[650px]">
                  <ChartPanel minHeight={600} />
                </div>
              </div>
            )}

            {currentSection === "positions" && (
              <div className="flex flex-col gap-4">
                <div className="min-h-[500px]">
                  <PositionsPanel />
                </div>
              </div>
            )}

            {currentSection === "analytics" && (
              <div className="flex flex-col gap-4">
                <AnalyticsPanel />
              </div>
            )}

            {currentSection === "journal" && (
              <div className="flex flex-col gap-4">
                <div className="w-full min-h-[550px]">
                  <JournalTable />
                </div>
              </div>
            )}

            {currentSection === "risk" && (
              <div className="max-w-3xl mx-auto">
                <RiskConfigPanel />
              </div>
            )}

            {currentSection === "logs" && (
              <div className="h-[calc(100vh-130px)] min-h-[500px]">
                <LiveLogFeed />
              </div>
            )}
          </div>
        </main>
      </div>

      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  );
}

export default App;
