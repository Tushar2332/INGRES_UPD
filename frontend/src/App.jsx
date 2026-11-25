import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatWindow from './components/ChatWindow';
import Sidebar from './components/Sidebar';
import WhatIfPanel from './components/WhatIfPanel';
import DiagnosticPanel from './components/DiagnosticPanel';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [language, setLanguage]                 = useState('en');
  const [states, setStates]                     = useState([]);
  const [selectedState, setSelectedState]       = useState(null);
  const [activeTab, setActiveTab]               = useState('chat'); // 'chat' | 'whatif' | 'diagnostics'
  const [diagnosticTarget, setDiagnosticTarget] = useState(null);
  const [whatIfTarget, setWhatIfTarget]         = useState(null);

  useEffect(() => {
    axios.get(`${API_URL}/states`)
      .then(r => setStates(r.data))
      .catch(err => console.error('Error fetching states:', err));
  }, []);

  const handleOpenDiagnostics = (state, district) => {
    setDiagnosticTarget({ state, district, ts: Date.now() });
    setActiveTab('diagnostics');
  };

  const handleOpenWhatIf = (state, district) => {
    setWhatIfTarget({ state, district, ts: Date.now() });
    setActiveTab('whatif');
  };

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
                <span className="header-badge diag-badge">🩺 Evidence Diagnostics</span>
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
            <button
              id="tab-diagnostics"
              className={`tab-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
              onClick={() => setActiveTab('diagnostics')}
            >
              🩺 Diagnostics
            </button>
          </nav>
        </header>

        {/* Tab Content (keep panes mounted to preserve state across tab switches) */}
        <div className="tab-content">
          <div className={`tab-pane ${activeTab === 'chat' ? 'active' : 'hidden'}`}>
            <ChatWindow
              language={language}
              selectedState={selectedState}
            />
          </div>
          <div className={`tab-pane ${activeTab === 'whatif' ? 'active' : 'hidden'}`}>
            <div className="whatif-container">
              <WhatIfPanel
                externalTarget={whatIfTarget}
                onOpenDiagnostics={handleOpenDiagnostics}
              />
            </div>
          </div>
          <div className={`tab-pane ${activeTab === 'diagnostics' ? 'active' : 'hidden'}`}>
            <div className="whatif-container">
              <DiagnosticPanel
                externalTarget={diagnosticTarget}
                onOpenWhatIf={handleOpenWhatIf}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
