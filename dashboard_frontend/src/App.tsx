import { Toaster } from "sonner";
import { StatusBar } from "./features/system-status/StatusBar";
import { ChartPanel } from "./features/chart/ChartPanel";
import { PositionsPanel } from "./features/positions/PositionsPanel";
import { AnalyticsPanel } from "./features/analytics/AnalyticsPanel";
import { JournalTable } from "./features/journal/JournalTable";
import { RiskConfigPanel } from "./features/risk-config/RiskConfigPanel";
import { LiveLogFeed } from "./features/live-log/LiveLogFeed";

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground dark flex flex-col">
      <StatusBar />
      
      <div className="flex-1 p-4 md:p-6 overflow-hidden flex flex-col gap-6">
        {/* Top Row: Chart & Positions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-6 min-h-[400px]">
          <ChartPanel />
          <div className="col-span-1 lg:col-span-1 flex flex-col gap-6 h-full">
            <PositionsPanel />
          </div>
        </div>
        
        {/* Middle Row: Analytics */}
        <div className="min-h-[350px]">
          <AnalyticsPanel />
        </div>
        
        {/* Journal Full Width Row */}
        <div className="w-full min-h-[500px]">
          <JournalTable />
        </div>

        {/* Bottom Row: Risk Config, Logs */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[400px]">
          <div className="col-span-1 h-[400px] lg:h-auto">
            <RiskConfigPanel />
          </div>
          <div className="col-span-1 h-[400px] lg:h-auto">
            <LiveLogFeed />
          </div>
        </div>
      </div>
      
      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}

export default App;
