import React, { useState, useEffect, useMemo } from 'react';
import { useEvents } from '../contexts/EventContext';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import './EquityCurve.css';

const STARTING_BALANCE = 10000;

const EquityCurve = () => {
  const { subscribe } = useEvents();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  // Initial load
  useEffect(() => {
    fetch('http://localhost:8000/api/equity-curve')
      .then(res => res.json())
      .then(json => {
        if (json.data && json.data.length > 0) {
          setData(json.data);
        } else {
          // Empty state
          setData([{
            entry_time: new Date().toISOString(),
            equity: STARTING_BALANCE,
            pnl: 0,
            cumulative_pnl: 0
          }]);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch equity curve", err);
        setLoading(false);
      });
  }, []);

  // Live updates
  useEffect(() => {
    const unsub = subscribe('trade_closed', (eventData) => {
      setData(prev => {
        const lastEntry = prev[prev.length - 1] || { equity: STARTING_BALANCE, cumulative_pnl: 0 };
        // Handle pnl_usd from event or pnl from DB
        const newPnl = eventData.pnl_usd !== undefined ? eventData.pnl_usd : (eventData.pnl || 0);
        const newCumulative = lastEntry.cumulative_pnl + newPnl;
        const newEquity = STARTING_BALANCE + newCumulative;
        
        return [...prev, {
          entry_time: new Date().toISOString(), // Approximation for real-time update
          equity: newEquity,
          pnl: newPnl,
          cumulative_pnl: newCumulative
        }];
      });
    });

    return () => unsub();
  }, [subscribe]);

  // Compute Max Drawdown threshold
  const maxDrawdownThreshold = useMemo(() => {
    if (data.length === 0) return STARTING_BALANCE * 0.9;
    const peak = Math.max(...data.map(d => d.equity));
    return peak * 0.9; // 10% DD
  }, [data]);

  const currentEquity = data.length > 0 ? data[data.length - 1].equity : STARTING_BALANCE;
  const isDrawdownBreached = currentEquity <= maxDrawdownThreshold;

  const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  const formatTime = (timeStr) => {
    const d = new Date(timeStr);
    return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  if (loading) return <div className="equity-curve-container">Loading Equity Curve...</div>;

  return (
    <div className="equity-curve-container">
      <div className="ec-header">
        <h2>Equity Curve (Paper)</h2>
        <div className="ec-stats">
          <span>Current: <strong className={isDrawdownBreached ? 'text-danger' : 'text-success'}>{formatCurrency(currentEquity)}</strong></span>
          <span>10% DD Limit: <strong>{formatCurrency(maxDrawdownThreshold)}</strong></span>
        </div>
      </div>
      
      <div className="ec-chart">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis 
              dataKey="entry_time" 
              tickFormatter={formatTime} 
              stroke="#8c8c9e" 
              fontSize={12} 
              minTickGap={30}
            />
            <YAxis 
              domain={['auto', 'auto']} 
              tickFormatter={(v) => `$${v}`}
              stroke="#8c8c9e" 
              fontSize={12}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: 'rgba(30,30,40,0.9)', border: '1px solid #444', borderRadius: '8px' }}
              labelFormatter={formatTime}
              formatter={(value) => [formatCurrency(value), 'Equity']}
            />
            <ReferenceLine 
              y={maxDrawdownThreshold} 
              label={{ position: 'insideBottomRight', value: '10% DD Limit', fill: '#ff4d4f', fontSize: 12 }} 
              stroke="#ff4d4f" 
              strokeDasharray="5 5" 
            />
            <Line 
              type="monotone" 
              dataKey="equity" 
              stroke="#00f2fe" 
              strokeWidth={3} 
              dot={false}
              activeDot={{ r: 6, fill: '#00f2fe', stroke: '#fff', strokeWidth: 2 }} 
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default EquityCurve;
