import React from 'react';
import { useEvents } from './contexts/EventContext';
import StatusHeader from './components/StatusHeader';
import StatsPanel from './components/StatsPanel';
import EquityCurve from './components/EquityCurve';
import TradeList from './components/TradeList';
import './App.css';

function App() {
  const { isConnected, reconnectAttempts } = useEvents();

  return (
    <div className="App">
      {!isConnected && (
        <div className="reconnect-banner">
          ⚠️ Disconnected from live feed. 
          {reconnectAttempts > 0 ? ` Reconnecting (Attempt ${reconnectAttempts})...` : ' Connection lost.'}
        </div>
      )}
      <header className="App-header">
        <h1>SMC Zero-Latency Dashboard</h1>
      </header>
      <main className="App-main">
        <StatusHeader />
        <StatsPanel />
        <EquityCurve />
        <TradeList />
      </main>
    </div>
  );
}

export default App;
