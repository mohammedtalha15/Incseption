class WebSocketManager {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.listeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnects = 5;
    this.isConnected = false;
    this.pingInterval = null;
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log(`[WS] Connected to ${this.url}`);
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      if (event.data === 'pong') return;
      try {
        const data = JSON.parse(event.data);
        this.notifyListeners(data);
      } catch (err) {
        console.error('[WS] Message parsing error:', err);
      }
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.stopPing();
      this.attemptReconnect();
    };

    this.ws.onerror = (err) => {
      console.error('[WS] Connection error:', err);
    };
  }

  startPing() {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000);
  }

  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnects) {
      setTimeout(() => {
        this.reconnectAttempts++;
        console.log(`[WS] Reconnecting... (Attempt ${this.reconnectAttempts})`);
        this.connect();
      }, Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000));
    }
  }

  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners(data) {
    this.listeners.forEach((cb) => cb(data));
  }

  disconnect() {
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// REST API Methods (Using fetch since axios is optional and fetch is native in Next.js)
const API_BASE = 'http://localhost:8000';

export const api = {
  async getHistoricalReadings(patientId, hours = 6) {
    const res = await fetch(`${API_BASE}/readings/${patientId}?hours=${hours}`);
    if (!res.ok) throw new Error('Failed to fetch readings');
    return res.json();
  },

  async getRecentAlerts(patientId, limit = 50) {
    const res = await fetch(`${API_BASE}/alerts/${patientId}?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch alerts');
    return res.json();
  },

  async getPatients() {
    const res = await fetch(`${API_BASE}/patients`);
    if (!res.ok) return []; // Graceful degradation if backend empty
    return res.json();
  },

  async startSimulator(speed = 5, interval = 2) {
    const res = await fetch(`${API_BASE}/simulator/start?speed=${speed}&interval=${interval}`, {
      method: 'POST'
    });
    return res.json();
  },

  async stopSimulator() {
    const res = await fetch(`${API_BASE}/simulator/stop`, {
      method: 'POST'
    });
    return res.json();
  }
};

export function createWebSocketHook(patientId) {
  let manager = null;

  return function usePatientWebSocket(onMessage) {
    const React = require('react');
    
    React.useEffect(() => {
      if (!patientId) return;

      if (!manager) {
        manager = new WebSocketManager(`ws://localhost:8000/ws/${patientId}`);
        manager.connect();
      }

      const unsubscribe = manager.subscribe(onMessage);

      return () => {
        unsubscribe();
        // Option to disconnect here if no other listeners
      };
    }, [patientId, onMessage]);

    return manager;
  };
}
