import React, { useState, useEffect, useCallback } from 'react';
import { useEvents } from '../contexts/EventContext';
import './StatsPanel.css';

const StatsPanel = () => {
  const { subscribe } = useEvents();
  const [stats, setStats] = useState({
    all_time: { trades: 0, win_rate: 0, expectancy: 0, pf: 0 },
    week: { trades: 0, win_rate: 0, expectancy: 0, pf: 0 }
  });
  const [startDate, setStartDate] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const [statsRes, statusRes] = await Promise.all([
        fetch('http://localhost:8000/api/stats'),
        fetch('http://localhost:8000/api/status')
      ]);
      const statsData = await statsRes.json();
      const statusData = await statusRes.json();

      if (!statsData.error) setStats(statsData);
      if (statusData.paper_start_date) {
        setStartDate(new Date(statusData.paper_start_date));
      }
      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch stats", err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    // Recompute/refetch on new trade closed
    const unsub = subscribe('trade_closed', () => {
      // Re-fetching is the most robust way to ensure aggregations are perfect
      fetchStats();
    });
    return () => unsub();
  }, [subscribe, fetchStats]);

  const evaluateCriteria = () => {
    if (!startDate) return { status: 'pending', text: 'Waiting for first trade...' };
    
    const weeksActive = (new Date() - startDate) / (1000 * 60 * 60 * 24 * 7);
    const exp = stats.all_time.expectancy;
    const trades = stats.all_time.trades;

    if (trades === 0) return { status: 'pending', text: 'No trades yet' };

    // Criteria: Expectancy > +0.05R, Duration 4-6 weeks
    if (weeksActive > 6) {
      return { status: 'failed', text: 'Failed: Duration exceeded 6 weeks' };
    }
    
    if (weeksActive >= 4 && exp <= 0.05) {
      return { status: 'failed', text: 'Failed: Exp <= +0.05R after 4 weeks' };
    }

    if (exp > 0.05) {
      if (weeksActive >= 4) return { status: 'passed', text: 'Passed: Criteria Met!' };
      return { status: 'on-track', text: 'On Track (Duration < 4w)' };
    }

    return { status: 'at-risk', text: 'At Risk: Exp <= +0.05R' };
  };

  if (loading) return <div className="stats-panel-container">Loading stats...</div>;

  const criteria = evaluateCriteria();

  const renderStatGroup = (title, data) => (
    <div className="stat-group">
      <h3>{title}</h3>
      <div className="stat-grid">
        <div className="stat-box">
          <span className="stat-label">Trades</span>
          <span className="stat-value">{data.trades}</span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Win Rate</span>
          <span className="stat-value">{data.win_rate}%</span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Expectancy</span>
          <span className={`stat-value ${data.expectancy > 0 ? 'text-success' : 'text-danger'}`}>
            {data.expectancy > 0 ? '+' : ''}{data.expectancy}R
          </span>
        </div>
        <div className="stat-box">
          <span className="stat-label">Profit Factor</span>
          <span className={`stat-value ${data.pf >= 1 ? 'text-success' : 'text-danger'}`}>
            {data.pf === Infinity ? 'INF' : data.pf}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="stats-panel-container">
      <div className="sp-header">
        <h2>Performance Stats</h2>
        <div className={`criteria-indicator status-${criteria.status}`}>
          <span className="indicator-dot"></span>
          {criteria.text}
        </div>
      </div>
      
      <div className="sp-content">
        {renderStatGroup('All-Time', stats.all_time)}
        {renderStatGroup('Current Week', stats.week)}
      </div>
    </div>
  );
};

export default StatsPanel;
