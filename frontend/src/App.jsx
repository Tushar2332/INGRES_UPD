import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatWindow from './components/ChatWindow';
import Sidebar from './components/Sidebar';
import WhatIfPanel from './components/WhatIfPanel';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [language, setLanguage]       = useState('en');
  const [states, setStates]           = useState([]);
  const [selectedState, setSelectedState] = useState(null);
  const [activeTab, setActiveTab]     = useState('chat'); // 'chat' | 'whatif'

  useEffect(() => {
    axios.get(`${API_URL}/states`)
      .then(r => setStates(r.data))
      .catch(err => console.error('Error fetching states:', err));
  }, []);

  return (
    <div className="app-container">
      <Sidebar
        states={states}
        language={language}
        setLanguage={setLanguage}
        onStateSelect={(state) => {
          setSelectedState(state);
          setActiveTab('chat');   // switch to chat when a state is selected
        }}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <div className="main-content">
        {/* Header */}
        <header className="app-header">
          <div className="header-gradient">
            <div className="header-inner">
              <div className="header-title-block">
                <h1>🌊 INGRES AI Assistant</h1>
                <p>Intelligent Groundwater Resource &amp; Environmental System</p>
              </div>
              <div className="header-badges">
                <span className="header-badge verified-badge">✓ Verified Answers</span>
                <span className="header-badge scope-badge">🛡️ Scope-Aware</span>
                <span className="header-badge whatif-badge">🔬 What-If Analysis</span>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <nav className="tab-nav">
            <button
              id="tab-chat"
              className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              💬 Chat
            </button>
            <button
              id="tab-whatif"
              className={`tab-btn ${activeTab === 'whatif' ? 'active' : ''}`}
              onClick={() => setActiveTab('whatif')}
            >
              🔬 What-If Analysis
            </button>
          </nav>
        </header>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'chat' && (
            <ChatWindow
              language={language}
              selectedState={selectedState}
            />
          )}
          {activeTab === 'whatif' && (
            <div className="whatif-container">
              <WhatIfPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
