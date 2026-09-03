import React, { useState, useEffect } from 'react';
import { useEvents } from '../contexts/EventContext';
import './StatusHeader.css';

const POLL_INTERVAL_MS = 15000; // 15s interval, so >30s is stale

const StatusHeader = () => {
  const { isConnected, subscribe } = useEvents();
  const [status, setStatus] = useState(null);
  const [lastHeartbeat, setLastHeartbeat] = useState(null);
  const [lastSignal, setLastSignal] = useState(null);
  const [activeInstruments, setActiveInstruments] = useState([]);
  const [isStale, setIsStale] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch initial REST data
  useEffect(() => {
    fetch('http://localhost:8000/api/status')
      .then(res => res.json())
      .then(data => {
        setStatus(data);
        if (data.heartbeat) {
          setLastHeartbeat(new Date(data.heartbeat.timestamp));
        }
        if (data.last_signal) {
          setLastSignal(data.last_signal);
        }
        if (data.active_instruments) {
          setActiveInstruments(data.active_instruments);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch initial status", err);
        setLoading(false);
      });
  }, []);

  // Subscribe to live events
  useEffect(() => {
    const unsubHeartbeat = subscribe('heartbeat', (data) => {
      setLastHeartbeat(new Date(data.timestamp));
      if (data.extra_info?.active_symbols) {
        setActiveInstruments(data.extra_info.active_symbols);
      }
    });

    const unsubSignal = subscribe('signal_checked', (data) => {
      setLastSignal({
        timestamp: data.timestamp,
        symbol: data.symbol,
        signal_type: data.signal_type,
        result: data.result || 'checked'
      });
    });

    return () => {
      unsubHeartbeat();
      unsubSignal();
    };
  }, [subscribe]);

  // Check staleness
  useEffect(() => {
    const interval = setInterval(() => {
      if (!lastHeartbeat) return;
      const now = new Date();
      const diff = now - lastHeartbeat;
      setIsStale(diff > POLL_INTERVAL_MS * 2);
    }, 5000);
    return () => clearInterval(interval);
  }, [lastHeartbeat]);

  if (loading) return <div className="status-header">Loading status...</div>;

  const getSystemState = () => {
    if (isStale) return <span className="badge badge-stale">Stale / Stopped</span>;
    if (isConnected) return <span className="badge badge-live">Live</span>;
    return <span className="badge badge-offline">Offline</span>;
  };

  return (
    <div className="status-header">
      <div className="status-section">
        <h2>System Status</h2>
        <div className="status-row">
          <span className="label">State:</span>
          {getSystemState()}
        </div>
        <div className="status-row">
          <span className="label">WebSocket:</span>
          <span style={{ color: isConnected ? '#4caf50' : '#f44336' }}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
      
      <div className="status-section">
        <h2>Heartbeat</h2>
        <div className="status-row">
          <span className="label">Last Heartbeat:</span>
          <span>{lastHeartbeat ? lastHeartbeat.toLocaleTimeString() : 'N/A'}</span>
        </div>
        <div className="status-row">
          <span className="label">Active Instruments:</span>
          <span>{activeInstruments.length > 0 ? activeInstruments.join(', ') : 'None'}</span>
        </div>
      </div>

      <div className="status-section">
        <h2>Last Signal Check</h2>
        <div className="status-row">
          <span className="label">Time:</span>
          <span>
            {lastSignal?.timestamp 
              ? new Date(lastSignal.timestamp).toLocaleTimeString() 
              : 'N/A'}
          </span>
        </div>
        <div className="status-row">
          <span className="label">Details:</span>
          <span className="signal-details">
            {lastSignal 
              ? `${lastSignal.symbol || ''} - ${lastSignal.signal_type || ''} (${lastSignal.result || ''})` 
              : 'No signals yet'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default StatusHeader;
