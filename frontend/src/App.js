import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import SystemStatus from './components/SystemStatus';
import Chat from './components/Chat';
import Sidebar from './components/Sidebar';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [recentQuestions, setRecentQuestions] = useState([]);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const [commonQuestions, setCommonQuestions] = useState({});
  const [knowledgeStats, setKnowledgeStats] = useState({});
  const [systemStatus, setSystemStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState(null);
  const [awaitingRepeat, setAwaitingRepeat] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchCommonQuestions();
    fetchKnowledgeStats();
    fetchSystemStatus();
    
    const interval = setInterval(fetchSystemStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (pendingQuestion) {
      handleSendMessage(pendingQuestion);
      setPendingQuestion(null);
    }
  }, [pendingQuestion]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/system-status`);
      setSystemStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    }
  };

  const fetchCommonQuestions = async () => {
    try {
      const response = await axios.get(`${API_BASE}/common-questions`);
      setCommonQuestions(response.data);
    } catch (error) {
      console.error('Failed to fetch common questions:', error);
    }
  };

  const fetchKnowledgeStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/knowledge-stats`);
      setKnowledgeStats(response.data);
    } catch (error) {
      console.error('Failed to fetch knowledge stats:', error);
    }
  };

  const handleSendMessage = async (text) => {
    const prompt = text.trim();
    
    if (awaitingRepeat) {
      const lower = prompt.toLowerCase();
      if (['yes', 'y', 'yeah', 'yep', 'sure', 'ok', 'please'].includes(lower)) {
        if (lastResponse) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: lastResponse.content,
            sources: lastResponse.sources || [],
            metadata: lastResponse.metadata || {}
          }]);
        }
        setAwaitingRepeat(false);
        return;
      } else {
        setAwaitingRepeat(false);
      }
    }

    const recentQs = recentQuestions;
    if (recentQs.includes(prompt)) {
      const duplicateMsg = "You've asked me that this session. If you'd like me to say it again, just say yes, otherwise I'll await your next question or clarification.";
      
      setMessages(prev => [...prev, { role: 'user', content: prompt }]);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: duplicateMsg, 
        sources: [], 
        metadata: {} 
      }]);
      setAwaitingRepeat(true);
      return;
    }

    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setRecentQuestions(prev => [...prev.slice(-99), prompt]);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/chat`, {
        message: prompt,
        session_history: sessionHistory,
        recent_questions: recentQuestions
      });

      const data = response.data;
      
      if (data.is_statement) {
        setSessionHistory(prev => [...prev, { content: prompt, input_type: 'statement' }]);
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.acknowledgement, 
          sources: [], 
          metadata: { is_statement: true } 
        }]);
      } else {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer, 
          sources: data.sources || [], 
          metadata: { 
            model_used: data.model_used, 
            latency: data.latency_ms,
            used_sql: data.used_sql 
          } 
        }]);
        setLastResponse({ content: data.answer, sources: data.sources, metadata: data.metadata });
      }
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Error: ${error.response?.data?.detail || error.message}`, 
        sources: [], 
        metadata: { error: true } 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearSession = () => {
    setMessages([]);
    setSessionHistory([]);
    setRecentQuestions([]);
    setLastResponse(null);
    setAwaitingRepeat(false);
  };

  const handleSelectQuestion = (question) => {
    setPendingQuestion(question);
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🎖️ DVA Assistant</h1>
        <p>Ask questions about Australian veteran entitlements and benefits</p>
      </header>
      
      <div className="main-container">
        <div className="chat-container">
          <Chat 
            messages={messages} 
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            chatEndRef={chatEndRef}
          />
        </div>
        
        <aside className="sidebar">
          <SystemStatus status={systemStatus} />
          
          <Sidebar 
            commonQuestions={commonQuestions}
            onSelectQuestion={handleSelectQuestion}
            recentQuestions={recentQuestions}
            sessionHistory={sessionHistory}
            knowledgeStats={knowledgeStats}
            onClearSession={handleClearSession}
          />
        </aside>
      </div>
    </div>
  );
}

export default App;
