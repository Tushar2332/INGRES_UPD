import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';
import CGWBBadge from './CGWBBadge';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * WhatIfPanel — dedicated What-If Analysis simulator.
 * Allows users to pick a district and simulate extraction changes.
 */
const WhatIfPanel = () => {
  const [states, setStates]           = useState([]);
  const [districts, setDistricts]     = useState([]);
  const [selectedState, setSelectedState]     = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [currentData, setCurrentData]  = useState(null);
  const [pctChange, setPctChange]      = useState(-15);
  const [result, setResult]            = useState(null);
  const [loading, setLoading]          = useState(false);
  const [error, setError]              = useState('');
  const [loadingDistricts, setLoadingDistricts] = useState(false);

  // Fetch states on mount
  useEffect(() => {
    axios.get(`${API_URL}/states`)
      .then(r => setStates(r.data))
      .catch(() => setError('Could not load states.'));
  }, []);

  // Fetch districts when state changes
  useEffect(() => {
    if (!selectedState) { setDistricts([]); return; }
    setLoadingDistricts(true);
    setSelectedDistrict('');
    setCurrentData(null);
    setResult(null);
    axios.get(`${API_URL}/districts/${encodeURIComponent(selectedState)}`)
      .then(r => { setDistricts(r.data); setLoadingDistricts(false); })
      .catch(() => { setError('Could not load districts.'); setLoadingDistricts(false); });
  }, [selectedState]);

  // Fetch current district data when district changes
  useEffect(() => {
    if (!selectedState || !selectedDistrict) { setCurrentData(null); return; }
    axios.get(`${API_URL}/data/${encodeURIComponent(selectedState)}`)
      .then(r => {
        const rec = r.data.find(d =>
          d.district.toUpperCase() === selectedDistrict.toUpperCase()
        );
        setCurrentData(rec || null);
        setResult(null);
      })
      .catch(() => setCurrentData(null));
  }, [selectedState, selectedDistrict]);

  const handleCalculate = async () => {
    if (!selectedState || !selectedDistrict) {
      setError('Please select a state and district first.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await axios.post(`${API_URL}/whatif`, {
        state: selectedState,
        district: selectedDistrict,
        pct_change: pctChange,
      });
      setResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Simulation failed. The district may lack required data.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const getBarColor = (stage) => {
    if (stage <= 70) return '#10b981';
    if (stage <= 90) return '#f59e0b';
    if (stage <= 100) return '#f97316';
    return '#ef4444';
  };

  const formatPctLabel = (v) => {
    return v < 0 ? `${Math.abs(v)}% reduction` : `${v}% increase`;
  };

  return (
    <div className="whatif-panel">
      {/* Header */}
      <div className="whatif-header">
        <h2>🔬 What-If Analysis</h2>
        <p>Simulate the effect of changing groundwater extraction on stage and CGWB category.</p>
      </div>

      {/* Controls */}
      <div className="whatif-controls">
        {/* State Selector */}
        <div className="control-group">
          <label className="control-label">📍 State</label>
          <select
            className="whatif-select"
            value={selectedState}
            onChange={e => setSelectedState(e.target.value)}
          >
            <option value="">— Select State —</option>
            {states.map(s => (
              <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>
            ))}
          </select>
        </div>

        {/* District Selector */}
        <div className="control-group">
          <label className="control-label">🏘️ District</label>
          <select
            className="whatif-select"
            value={selectedDistrict}
            onChange={e => setSelectedDistrict(e.target.value)}
            disabled={!selectedState || loadingDistricts}
          >
            <option value="">— Select District —</option>
            {districts.map(d => (
              <option key={d} value={d}>{d.charAt(0) + d.slice(1).toLowerCase()}</option>
            ))}
          </select>
          {loadingDistricts && <span className="loading-hint">Loading...</span>}
        </div>

        {/* Percentage Change Slider */}
        <div className="control-group full-width">
          <label className="control-label">
            🔧 Extraction Change: <strong>{formatPctLabel(pctChange)}</strong>
          </label>
          <div className="slider-row">
            <span className="slider-label red">-80%</span>
            <input
              type="range"
              min="-80"
              max="100"
              step="1"
              value={pctChange}
              onChange={e => setPctChange(Number(e.target.value))}
              className="whatif-slider"
            />
            <span className="slider-label green">+100%</span>
          </div>
          <div className="slider-value-row">
            <input
              type="number"
              min="-80"
              max="100"
              value={pctChange}
              onChange={e => setPctChange(Number(e.target.value))}
              className="pct-input"
            />
            <span className="pct-unit">%</span>
            <span className="pct-hint">
              {pctChange < 0 ? '(reduction)' : pctChange > 0 ? '(increase)' : '(no change)'}
            </span>
          </div>
        </div>

        {/* Calculate Button */}
        <button
          className="calculate-btn"
          onClick={handleCalculate}
          disabled={loading || !selectedState || !selectedDistrict}
        >
          {loading ? (
            <><span className="btn-spinner" /> Calculating...</>
          ) : (
            '⚡ Calculate What-If'
          )}
        </button>
      </div>

      {/* Current Data Preview */}
      {currentData && !result && (
        <div className="current-data-preview">
          <h4>📊 Current Data — {currentData.district?.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())}</h4>
          <div className="preview-grid">
            {currentData.extraction_stage !== null && (
              <div className="preview-item">
                <span className="preview-label">Stage of Extraction</span>
                <span className="preview-value">{currentData.extraction_stage?.toFixed(2)}%</span>
                <CGWBBadge category={currentData.cgwb_category} size="sm" />
              </div>
            )}
            {currentData.gw_extraction !== null && (
              <div className="preview-item">
                <span className="preview-label">GW Extraction</span>
                <span className="preview-value">{currentData.gw_extraction?.toFixed(2)} ham</span>
              </div>
            )}
            {currentData.annual_extractable !== null && (
              <div className="preview-item">
                <span className="preview-label">Annual Extractable</span>
                <span className="preview-value">{currentData.annual_extractable?.toFixed(2)} ham</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="whatif-error">⚠️ {error}</div>
      )}

      {/* Results */}
      {result && (
        <div className="whatif-results">
          <h3>📋 Simulation Results</h3>

          {/* Before / After Cards */}
          <div className="result-cards">
            <div className="result-card current-card">
              <div className="result-card-title">📊 Current State</div>
              <div className="result-stage" style={{ color: getBarColor(result.result.current_stage) }}>
                {result.result.current_stage?.toFixed(2)}%
              </div>
              <CGWBBadge category={result.result.current_category?.category} stage={result.result.current_stage} />
              <div className="result-detail">{result.result.current_extraction_ham?.toFixed(2)} ham extraction</div>
            </div>

            <div className="result-arrow">
              <div className="arrow-label">
                {pctChange < 0 ? '⬇️' : '⬆️'} {Math.abs(pctChange)}%
              </div>
              →
            </div>

            <div className={`result-card simulated-card ${result.result.category_changed ? 'category-changed' : ''}`}>
              <div className="result-card-title">🔮 Simulated State</div>
              <div className="result-stage" style={{ color: getBarColor(result.result.new_stage) }}>
                {result.result.new_stage?.toFixed(2)}%
              </div>
              <CGWBBadge category={result.result.new_category?.category} stage={result.result.new_stage} />
              <div className="result-detail">{result.result.new_extraction_ham?.toFixed(2)} ham extraction</div>
              {result.result.category_changed && (
                <div className="category-change-badge">✨ Category Changed!</div>
              )}
            </div>
          </div>

          {/* Bar Chart Comparison */}
          <div className="whatif-chart">
            <h4>📊 Stage Comparison</h4>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={result.chart_data?.data || []}
                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis
                  label={{ value: 'Stage (%)', angle: -90, position: 'insideLeft' }}
                  domain={[0, Math.max(150, (result.result.current_stage || 0) * 1.2)]}
                />
                <Tooltip formatter={(v) => `${v.toFixed(2)}%`} />
                <ReferenceLine y={70}  stroke="#10b981" strokeDasharray="4 4" label={{ value: 'Safe 70%', position: 'right', fontSize: 11 }} />
                <ReferenceLine y={90}  stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'Semi-Crit 90%', position: 'right', fontSize: 11 }} />
                <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Critical 100%', position: 'right', fontSize: 11 }} />
                <Bar dataKey="stage" name="Stage (%)" radius={[6, 6, 0, 0]}>
                  {(result.chart_data?.data || []).map((entry, idx) => (
                    <Cell key={idx} fill={getBarColor(entry.stage)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Guidance Text */}
          <div className="whatif-guidance">
            {result.result.reduction_needed_to_non_overexploited_pct != null && (
              <div className="guidance-item warning">
                💡 To exit <strong>Over-Exploited</strong> status (stage ≤100%), a
                <strong> {result.result.reduction_needed_to_non_overexploited_pct?.toFixed(1)}% </strong>
                extraction reduction is needed.
              </div>
            )}
            {result.result.reduction_needed_to_safe_pct != null && (
              <div className="guidance-item info">
                💡 To reach <strong>Safe</strong> category (stage ≤70%), a
                <strong> {result.result.reduction_needed_to_safe_pct?.toFixed(1)}% </strong>
                extraction reduction is required.
              </div>
            )}
            <div className="guidance-disclaimer">
              📋 Based on INGRES/CGWB assessment data ({result.assessment_year}).
              No database records were modified during this simulation.
            </div>
          </div>

          {/* Reset Button */}
          <button className="reset-btn" onClick={() => { setResult(null); setError(''); }}>
            🔄 Run Another Simulation
          </button>
        </div>
      )}

      {/* Instructions (shown when nothing is selected) */}
      {!currentData && !result && !loading && (
        <div className="whatif-instructions">
          <h4>How to use What-If Analysis</h4>
          <ol>
            <li>Select a <strong>state</strong> from the dropdown</li>
            <li>Select a <strong>district</strong> within the state</li>
            <li>Adjust the <strong>extraction change</strong> slider (negative = reduction)</li>
            <li>Click <strong>Calculate What-If</strong> to see the simulation</li>
          </ol>
          <div className="cgwb-legend">
            <h5>CGWB Category Reference</h5>
            <div className="legend-items">
              <span className="legend-item cgwb-safe">🟢 Safe ≤70%</span>
              <span className="legend-item cgwb-semi-critical">🟡 Semi-Critical 70–90%</span>
              <span className="legend-item cgwb-critical">🟠 Critical 90–100%</span>
              <span className="legend-item cgwb-over-exploited">🔴 Over-Exploited &gt;100%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WhatIfPanel;
