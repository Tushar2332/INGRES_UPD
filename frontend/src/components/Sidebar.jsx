import React, { useState } from 'react';
import { FaGlobe, FaChevronDown, FaChevronUp } from 'react-icons/fa';

const Sidebar = ({ states, language, setLanguage, onStateSelect, activeTab, setActiveTab }) => {
  const [showStates, setShowStates] = useState(false);

  const languages = [
    { code: 'en', name: 'English',    flag: '🇬🇧' },
    { code: 'hi', name: 'हिन्दी',    flag: '🇮🇳' },
    { code: 'kn', name: 'ಕನ್ನಡ',    flag: '🇮🇳' },
    { code: 'te', name: 'తెలుగు',   flag: '🇮🇳' },
    { code: 'ta', name: 'தமிழ்',    flag: '🇮🇳' },
    { code: 'mr', name: 'मराठी',    flag: '🇮🇳' },
    { code: 'bn', name: 'বাংলা',    flag: '🇮🇳' },
    { code: 'gu', name: 'ગુજરાતી',  flag: '🇮🇳' },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>🗺️ Navigation</h2>
      </div>

      {/* Language Selector */}
      <div className="sidebar-section">
        <h3><FaGlobe /> Language</h3>
        <select
          className="language-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          {languages.map(lang => (
            <option key={lang.code} value={lang.code}>
              {lang.flag} {lang.name}
            </option>
          ))}
        </select>
      </div>

      {/* Quick Nav Buttons */}
      {setActiveTab && (
        <div className="sidebar-section">
          <h3>⚡ Quick Access</h3>
          <button
            className={`state-item ${activeTab === 'chat' ? 'state-item-active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 Chat Assistant
          </button>
          <button
            className={`state-item ${activeTab === 'whatif' ? 'state-item-active' : ''}`}
            onClick={() => setActiveTab('whatif')}
          >
            🔬 What-If Analysis
          </button>
        </div>
      )}

      {/* States List */}
      <div className="sidebar-section">
        <div
          className="section-header"
          onClick={() => setShowStates(!showStates)}
        >
          <h3>📍 States ({states.length})</h3>
          {showStates ? <FaChevronUp /> : <FaChevronDown />}
        </div>

        {showStates && (
          <div className="states-list">
            {states.map(state => (
              <button
                key={state}
                className="state-item"
                onClick={() => onStateSelect(state)}
              >
                {state.charAt(0) + state.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <p>💧 Powered by AI</p>
        <p className="version">v3.0 (Review 2)</p>
        <p style={{ fontSize: '0.72rem', marginTop: '4px', color: '#9ca3af' }}>
          INGRES / CGWB · GEC-2022
        </p>
      </div>
    </div>
  );
};

export default Sidebar;
