import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';

const EventContext = createContext();

export const EventProvider = ({ children }) => {
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const ws = useRef(null);
  
  // Custom simple event bus logic
  const listeners = useRef(new Map());

  const subscribe = useCallback((eventType, callback) => {
    if (!listeners.current.has(eventType)) {
      listeners.current.set(eventType, new Set());
    }
    listeners.current.get(eventType).add(callback);

    // Return unsubscribe function
    return () => {
      const typeListeners = listeners.current.get(eventType);
      if (typeListeners) {
        typeListeners.delete(callback);
      }
    };
  }, []);

  const emit = useCallback((eventType, data) => {
    const typeListeners = listeners.current.get(eventType);
    if (typeListeners) {
      typeListeners.forEach((callback) => callback(data));
    }
  }, []);

  useEffect(() => {
    let reconnectTimer;
    let isMounted = true;

    const connectWs = () => {
      ws.current = new WebSocket('ws://localhost:8000/ws/live');
      
      ws.current.onopen = () => {
        if (!isMounted) return;
        setIsConnected(true);
        setReconnectAttempts(0);
        console.log('WebSocket connected to /ws/live');
      };
      
      ws.current.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          // Emit the event to specific listeners
          emit(payload.type, payload.data);
          
          // Also keep a log of recent events
          setEvents(prev => [...prev.slice(-49), payload]);
        } catch (err) {
          console.error("Error parsing WS message", err);
        }
      };
      
      ws.current.onclose = () => {
        if (!isMounted) return;
        setIsConnected(false);
        console.log('WebSocket disconnected');
        
        // Exponential backoff
        setReconnectAttempts(prev => {
          const nextAttempt = prev + 1;
          const delay = Math.min(1000 * Math.pow(2, nextAttempt), 30000);
          reconnectTimer = setTimeout(connectWs, delay);
          return nextAttempt;
        });
      };
      
      ws.current.onerror = (err) => {
        console.error('WebSocket error', err);
        ws.current.close();
      };
    };

    connectWs();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimer);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [emit]);

  const value = {
    isConnected,
    reconnectAttempts,
    subscribe,
    events
  };

  return (
    <EventContext.Provider value={value}>
      {children}
    </EventContext.Provider>
  );
};

export const useEvents = () => {
  return useContext(EventContext);
};
