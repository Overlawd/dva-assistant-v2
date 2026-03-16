import React, { useState } from 'react';
import './Sidebar.css';

const SOURCE_COLORS = {
  'DVA': '#1e40af',
  'CLIK': '#7c3aed',
  'Legislation': '#059669',
  'default': '#666'
};

function Sidebar({ 
  commonQuestions, 
  onSelectQuestion, 
  recentQuestions, 
  sessionHistory, 
  knowledgeStats,
  onClearSession 
}) {
  const [expandedSection, setExpandedSection] = useState(null);

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const allQuestions = [];
  if (commonQuestions) {
    Object.entries(commonQuestions).forEach(([category, questions]) => {
      questions.slice(0, 3).forEach(q => allQuestions.push(q));
    });
  }

  return (
    <div className="sidebar-content">
      <div className="sidebar-section">
        <button 
          className={`section-header ${expandedSection === 'questions' ? 'expanded' : ''}`}
          onClick={() => toggleSection('questions')}
        >
          <span>❓ Common Questions</span>
          <span className="arrow">{expandedSection === 'questions' ? '▼' : '▶'}</span>
        </button>
        
        {expandedSection === 'questions' && (
          <div className="section-content">
            <select 
              onChange={(e) => {
                if (e.target.value) onSelectQuestion(e.target.value);
              }}
              defaultValue=""
            >
              <option value="" disabled>Select a question...</option>
              {allQuestions.map((q, idx) => (
                <option key={idx} value={q}>{q}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="sidebar-section">
        <button 
          className={`section-header ${expandedSection === 'settings' ? 'expanded' : ''}`}
          onClick={() => toggleSection('settings')}
        >
          <span>⚙️ Settings</span>
          <span className="arrow">{expandedSection === 'settings' ? '▼' : '▶'}</span>
        </button>
        
        {expandedSection === 'settings' && (
          <div className="section-content">
            <div className="stat-item">
              <span>Recent Questions:</span>
              <span>{recentQuestions.length}</span>
            </div>
            
            {recentQuestions.length > 0 && (
              <div className="recent-list">
                <small>Recent:</small>
                {recentQuestions.slice(-5).map((q, idx) => (
                  <div key={idx} className="recent-item">• {q.substring(0, 40)}...</div>
                ))}
              </div>
            )}
            
            <div className="stat-item">
              <span>Session Context:</span>
              <span>{sessionHistory.length} statements</span>
            </div>
            
            <button className="clear-btn" onClick={onClearSession}>
              Clear Session
            </button>
          </div>
        )}
      </div>

      <div className="sidebar-section">
        <button 
          className={`section-header ${expandedSection === 'knowledge' ? 'expanded' : ''}`}
          onClick={() => toggleSection('knowledge')}
        >
          <span>📚 Knowledge Base</span>
          <span className="arrow">{expandedSection === 'knowledge' ? '▼' : '▶'}</span>
        </button>
        
        {expandedSection === 'knowledge' && (
          <div className="section-content">
            {Object.entries(knowledgeStats).length > 0 ? (
              Object.entries(knowledgeStats).map(([source, count]) => (
                <div key={source} className="stat-item">
                  <span style={{ color: SOURCE_COLORS[source] || SOURCE_COLORS.default }}>●</span>
                  <span>{source}:</span>
                  <span>{count}</span>
                </div>
              ))
            ) : (
              <p className="no-data">No data indexed</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Sidebar;
