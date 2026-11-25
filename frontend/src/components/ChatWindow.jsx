import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import MessageBubble from './MessageBubble';
import InputBar from './InputBar';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const _makeSessionId = () =>
  `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

const ChatWindow = ({ language, selectedState }) => {
  const sessionIdRef = useRef(_makeSessionId());
  const [chatContext, setChatContext] = useState(null);
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      text: "👋 Hello! I'm your **INGRES AI Assistant** — a Verified Groundwater & Irrigation Decision-Support Chatbot.\n\nAsk me about rainfall, extraction stages, CGWB categories, crop water suitability, irrigation impact, or groundwater sustainability for any Indian state or district. 💧",
      timestamp: new Date().toLocaleTimeString(),
      suggestions: [
        'What is the groundwater status of Mysuru?',
        'Karnataka groundwater',
        'Which crops require less water?',
        'Show all states',
        'Compare Karnataka and Maharashtra',
      ],
      verified: true,
      assessmentYear: '2024-2025',
      dataSource: 'INGRES / CGWB (GEC-2024-2025)',
      dataConfidence: 'Latest Available Assessment',
    }
  ]);
  const [isTyping, setIsTyping]  = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    const userMessage = {
      type: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        message: text,
        language: language,
        session_id: sessionIdRef.current,
        context: chatContext,
      });

      const d = response.data;
      if (d.context) {
        setChatContext(d.context);
      }
      const botMessage = {
        type:               'bot',
        text:               d.response,
        data:               d.data,
        suggestions:        d.suggestions,
        chartData:          d.chart_data,
        timestamp:          new Date().toLocaleTimeString(),
        // Review 2 fields
        verified:           d.verified,
        verificationIssues: d.verification_issues,
        scopeStatus:        d.scope_status,
        outOfScopeReason:   d.out_of_scope_reason,
        assessmentYear:     d.assessment_year,
        dataSource:         d.data_source,
        dataConfidence:     d.data_confidence,
        cgwbCategory:       d.cgwb_category,
        cgwbColor:          d.cgwb_color,
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          type:      'bot',
          text:      '😔 Sorry, I encountered an error. Please check that the backend is running and try again.',
          timestamp: new Date().toLocaleTimeString(),
        }
      ]);
      console.error('Chat error:', error);
    } finally {
      setIsTyping(false);
    }
  }, [language, chatContext]);

  useEffect(() => {
    if (selectedState) {
      sendMessage(`Tell me about ${selectedState}`);
    }
  }, [selectedState, sendMessage]);

  const handleSuggestionClick = (suggestion) => sendMessage(suggestion);

  return (
    <div className="chat-window">
      <div className="messages-container">
        {messages.map((msg, idx) => (
          <MessageBubble
            key={idx}
            message={msg}
            onSuggestionClick={handleSuggestionClick}
          />
        ))}

        {isTyping && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span /><span /><span />
            </div>
            <span className="typing-text">INGRES is thinking...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <InputBar onSend={sendMessage} language={language} />
    </div>
  );
};

export default ChatWindow;
