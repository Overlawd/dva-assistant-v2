import React, { useEffect, useState } from 'react';
import './SystemStatus.css';

const COLORS = {
  safe: '#22c55e',
  caution: '#eab308',
  warning: '#f97316',
  critical: '#ef4444'
};

function SystemStatus({ status }) {
  const [dismissedWarnings, setDismissedWarnings] = useState({});

  if (!status) {
    return (
      <div className="system-status">
        <h3>📊 System Status</h3>
        <p className="loading">Loading...</p>
      </div>
    );
  }

  const loadVal = status.load || 0;
  
  const getLoadColor = (load) => {
    if (load <= 50) return COLORS.safe;
    if (load <= 70) return COLORS.caution;
    if (load <= 90) return COLORS.warning;
    return COLORS.critical;
  };

  const loadColor = getLoadColor(loadVal);
  const warnings = status.warnings || [];

  const dismissWarning = (warning) => {
    setDismissedWarnings(prev => ({ ...prev, [warning]: true }));
  };

  const visibleWarnings = warnings.filter(w => !dismissedWarnings[w]);

  return (
    <div className="system-status">
      <h3>📊 System Status</h3>
      
      <div className="load-bar-container">
        <div className="load-bar-label">
          <span>Load</span>
          <span>{loadVal.toFixed(0)}%</span>
        </div>
        <div className="load-bar">
          <div 
            className="load-bar-fill" 
            style={{ width: `${loadVal}%`, backgroundColor: loadColor }}
          />
        </div>
      </div>

      {status.has_gpu ? (
        <div className="metrics-grid">
          <div className="metric">
            <span className="metric-label">GPU</span>
            <span className="metric-value">{status.gpu?.toFixed(0) || 0}%</span>
          </div>
          <div className="metric">
            <span className="metric-label">VRAM</span>
            <span className="metric-value">{status.vram?.toFixed(0) || 0}%</span>
          </div>
          <div className="metric">
            <span className="metric-label">Temp</span>
            <span className="metric-value">{status.gpu_temp || 0}°C</span>
          </div>
          <div className="metric">
            <span className="metric-label">Free</span>
            <span className="metric-value">{status.vram_free_gb?.toFixed(1) || 0}GB</span>
          </div>
        </div>
      ) : (
        <div className="metrics-grid">
          <div className="metric">
            <span className="metric-label">CPU</span>
            <span className="metric-value">{status.cpu?.toFixed(0) || 0}%</span>
          </div>
          <div className="metric">
            <span className="metric-label">Memory</span>
            <span className="metric-value">{status.memory?.toFixed(0) || 0}%</span>
          </div>
        </div>
      )}

      {visibleWarnings.length > 0 && (
        <div className="warnings">
          {visibleWarnings.map((warning, idx) => (
            <div key={idx} className="warning-banner">
              <span>⚠️ {warning}</span>
              <button onClick={() => dismissWarning(warning)}>✕</button>
            </div>
          ))}
        </div>
      )}

      <p className="update-note">🔄 Updates every 2 seconds</p>
    </div>
  );
}

export default SystemStatus;
