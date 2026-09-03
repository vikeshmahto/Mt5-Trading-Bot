import React, { useState, useEffect, useCallback } from 'react';
import { useEvents } from '../contexts/EventContext';
import './TradeList.css';

const TradeList = () => {
  const { subscribe } = useEvents();
  const [trades, setTrades] = useState([]);
  const [activeTrades, setActiveTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [signalType, setSignalType] = useState('');

  const fetchTrades = useCallback(() => {
    setLoading(true);
    let url = new URL('http://localhost:8000/api/trades');
    url.searchParams.append('limit', '50');
    if (startDate) url.searchParams.append('start_date', startDate);
    if (endDate) url.searchParams.append('end_date', endDate);
    if (signalType) url.searchParams.append('signal_type', signalType);

    fetch(url)
      .then(res => res.json())
      .then(json => {
        if (json.data) {
          setTrades(json.data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch trades", err);
        setLoading(false);
      });
  }, [startDate, endDate, signalType]);

  // Initial load & filter changes
  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  // Live updates
  useEffect(() => {
    const unsubOpened = subscribe('trade_opened', (eventData) => {
      setActiveTrades(prev => {
        // Avoid duplicates just in case
        if (prev.some(t => t.ticket === eventData.ticket)) return prev;
        return [{
          ticket: eventData.ticket,
          symbol: eventData.symbol,
          entry_time: eventData.entry_time || new Date().toISOString(),
          signal_type: eventData.signal_type || 'Unknown'
        }, ...prev];
      });
    });

    const unsubClosed = subscribe('trade_closed', (eventData) => {
      // Remove from active trades
      setActiveTrades(prev => prev.filter(t => t.ticket !== eventData.ticket));
      
      const newTrade = {
        id: eventData.ticket,
        mt5_ticket: eventData.ticket,
        symbol: eventData.symbol,
        entry_time: eventData.entry_time || new Date().toISOString(),
        exit_time: new Date().toISOString(),
        pnl: eventData.pnl_usd !== undefined ? eventData.pnl_usd : eventData.pnl,
        exit_reason: eventData.exit_reason,
        signal_type: eventData.signal_type || 'Unknown' 
      };

      setTrades(prev => [newTrade, ...prev]);
    });

    return () => {
      unsubOpened();
      unsubClosed();
    };
  }, [subscribe]);

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    fetchTrades();
  };

  const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleString();
  };

  return (
    <div className="trade-list-container">
      <div className="tl-header">
        <h2>Trade History</h2>
        
        <form className="tl-filters" onSubmit={handleFilterSubmit}>
          <div className="filter-group">
            <label>Start:</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div className="filter-group">
            <label>End:</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
          <div className="filter-group">
            <label>Type:</label>
            <select value={signalType} onChange={e => setSignalType(e.target.value)}>
              <option value="">All</option>
              <option value="momentum">Momentum</option>
              <option value="reversal">Reversal</option>
              <option value="breakout">Breakout</option>
            </select>
          </div>
          <button type="submit" className="filter-btn">Apply</button>
        </form>
      </div>

      <div className="tl-table-wrapper">
        {activeTrades.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#ff9800' }}>Active Open Trades</h3>
            <table className="tl-table" style={{ border: '1px solid #ff9800' }}>
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Entry Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {activeTrades.map(t => (
                  <tr key={t.ticket} style={{ background: 'rgba(255, 152, 0, 0.1)' }}>
                    <td>{t.ticket}</td>
                    <td>{t.symbol}</td>
                    <td><span className="type-badge">{t.signal_type}</span></td>
                    <td>{formatDate(t.entry_time)}</td>
                    <td style={{ color: '#ff9800', fontWeight: 'bold' }}>OPEN</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h3 style={{ margin: '0 0 10px 0', color: '#e0e0e0' }}>Closed Trades</h3>
        <table className="tl-table">
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Symbol</th>
              <th>Type</th>
              <th>Entry Time</th>
              <th>Exit Time</th>
              <th>Reason</th>
              <th>PnL</th>
            </tr>
          </thead>
          <tbody>
            {loading && trades.length === 0 ? (
              <tr><td colSpan="7" className="text-center">Loading trades...</td></tr>
            ) : trades.length === 0 ? (
              <tr><td colSpan="7" className="text-center">No trades found.</td></tr>
            ) : (
              trades.map((t, idx) => {
                const pnl = parseFloat(t.pnl || t.pnl_usd || 0);
                const isWin = pnl > 0;
                const isLoss = pnl < 0;
                
                let rowClass = '';
                if (isWin) rowClass = 'row-win';
                else if (isLoss) rowClass = 'row-loss';

                return (
                  <tr key={t.id || t.mt5_ticket || idx} className={rowClass}>
                    <td>{t.mt5_ticket}</td>
                    <td>{t.symbol}</td>
                    <td><span className="type-badge">{t.signal_type || '-'}</span></td>
                    <td>{formatDate(t.entry_time)}</td>
                    <td>{formatDate(t.exit_time)}</td>
                    <td>{t.exit_reason || '-'}</td>
                    <td className={`pnl-cell ${isWin ? 'text-success' : isLoss ? 'text-danger' : ''}`}>
                      {formatCurrency(pnl)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TradeList;
