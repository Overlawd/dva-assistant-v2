import React, { useState, useRef, useEffect } from 'react';
import './Chat.css';

const SOURCE_COLORS = {
  'DVA': '#1e40af',
  'CLIK': '#7c3aed',
  'Legislation': '#059669',
  'default': '#64748b'
};

function Chat({ messages, onSendMessage, isLoading, chatEndRef }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e);
    }
  };

  return (
    <div className="chat">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>👋 Welcome to DVA Assistant!</p>
            <p>Ask me anything about veteran entitlements, compensation, or benefits under MRCA, DRCA, or VEA.</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={idx} className={`message message-${msg.role}`}>
            <div className="message-content">
              <p>{msg.content}</p>
              
              {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  <details>
                    <summary>📋 Sources ({msg.sources.length})</summary>
                    <div className="sources-list">
                      {msg.sources.map((src, srcIdx) => (
                        <a 
                          key={srcIdx}
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: SOURCE_COLORS[src.source_type] || SOURCE_COLORS.default }}
                        >
                          [{srcIdx + 1}] {src.title}
                        </a>
                      ))}
                    </div>
                  </details>
                </div>
              )}
              
              {msg.role === 'assistant' && msg.metadata && Object.keys(msg.metadata).length > 0 && (
                <div className="message-meta">
                  {msg.metadata.model_used && <span>Model: {msg.metadata.model_used}</span>}
                  {msg.metadata.latency && <span>Latency: {msg.metadata.latency}</span>}
                  {msg.metadata.used_sql && <span>SQL: Yes</span>}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="message message-assistant">
            <div className="message-content">
              <div className="loading-indicator">
                <span>🤔 Thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={chatEndRef} />
      </div>
      
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about DVA entitlements..."
          disabled={isLoading}
        />
        <button type="submit" disabled={!input.trim() || isLoading}>
          Send
        </button>
      </form>
    </div>
  );
}

export default Chat;
