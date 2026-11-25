import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';
import CGWBBadge from './CGWBBadge';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PRESET_SCENARIOS = [
  { name: 'Scenario A: Irrigation -20%', irrigation_pct_change: -20, domestic_pct_change: 0, industrial_pct_change: 0 },
  { name: 'Scenario B: Irr -15% + Dom -10%', irrigation_pct_change: -15, domestic_pct_change: -10, industrial_pct_change: 0 },
  { name: 'Scenario C: Irr -20% + Ind -10% + Dom -5%', irrigation_pct_change: -20, domestic_pct_change: -5, industrial_pct_change: -10 },
];

/**
 * WhatIfPanel — What-If Analysis simulator supporting both uniform total-extraction
 * simulation (/whatif) and sector-wise multi-scenario comparison (/whatif/scenarios).
 */
const WhatIfPanel = ({ externalTarget, onOpenDiagnostics }) => {
  const [states, setStates]           = useState([]);
  const [districts, setDistricts]     = useState([]);
  const [selectedState, setSelectedState]     = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [pendingDistrict, setPendingDistrict]   = useState('');
  const [currentData, setCurrentData]  = useState(null);
  const [pctChange, setPctChange]      = useState(-15);
  const [result, setResult]            = useState(null);
  const [loading, setLoading]          = useState(false);
  const [error, setError]              = useState('');
  const [loadingDistricts, setLoadingDistricts] = useState(false);

  // Sector-wise multi-scenario controls
  const [irrPct, setIrrPct]             = useState(-20);
  const [domPct, setDomPct]             = useState(-10);
  const [indPct, setIndPct]             = useState(0);
  const [scenarioName, setScenarioName] = useState('Custom Sector Scenario');
  const [scenarioQueue, setScenarioQueue] = useState(PRESET_SCENARIOS);
  const [multiResult, setMultiResult]   = useState(null);
  const [multiLoading, setMultiLoading] = useState(false);
  const [multiError, setMultiError]     = useState('');

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
    setMultiResult(null);
    axios.get(`${API_URL}/districts/${encodeURIComponent(selectedState)}`)
      .then(r => { setDistricts(r.data); setLoadingDistricts(false); })
      .catch(() => { setError('Could not load districts.'); setLoadingDistricts(false); });
  }, [selectedState]);

  // Accept handoff from DiagnosticPanel
  useEffect(() => {
    if (externalTarget && externalTarget.state && externalTarget.district) {
      setSelectedState(externalTarget.state);
      setPendingDistrict(externalTarget.district);
    }
  }, [externalTarget]);

  useEffect(() => {
    if (pendingDistrict && districts.length > 0) {
      const match = districts.find(d => d.toUpperCase() === pendingDistrict.toUpperCase());
      if (match) {
        setSelectedDistrict(match);
        setPendingDistrict('');
      }
    }
  }, [pendingDistrict, districts]);

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
        setMultiResult(null);
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

  const handleAddCustomScenario = () => {
    if (scenarioQueue.length >= 10) {
      setMultiError('Maximum 10 scenarios can be compared at once.');
      return;
    }
    setMultiError('');
    const label = scenarioName.trim() || `Custom (Irr ${irrPct}%, Dom ${domPct}%, Ind ${indPct}%)`;
    setScenarioQueue(prev => [
      ...prev,
      {
        name: label,
        irrigation_pct_change: irrPct,
        domestic_pct_change: domPct,
        industrial_pct_change: indPct,
      },
    ]);
  };

  const handleRemoveScenario = (idx) => {
    setScenarioQueue(prev => prev.filter((_, i) => i !== idx));
  };

  const handleRunMultiScenario = async () => {
    if (!selectedState || !selectedDistrict) {
      setMultiError('Please select a state and district first.');
      return;
    }
    if (scenarioQueue.length === 0) {
      setMultiError('Add at least one scenario to compare.');
      return;
    }
    setMultiLoading(true);
    setMultiError('');
    try {
      const res = await axios.post(`${API_URL}/whatif/scenarios`, {
        state: selectedState,
        district: selectedDistrict,
        scenarios: scenarioQueue,
      });
      setMultiResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Multi-sector simulation failed.';
      setMultiError(msg);
    } finally {
      setMultiLoading(false);
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
      {currentData && (
        <div className="current-data-preview">
          <div className="preview-header-row">
            <h4>📊 Current Data — {currentData.district?.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())}</h4>
            {onOpenDiagnostics && (
              <button
                className="secondary-action-btn"
                onClick={() => onOpenDiagnostics(selectedState, selectedDistrict)}
              >
                🩺 Open Full Evidence Diagnostics
              </button>
            )}
          </div>
          <div className="preview-grid">
            {currentData.extraction_stage !== null && currentData.extraction_stage !== undefined && (
              <div className="preview-item">
                <span className="preview-label">Official CGWB Stage</span>
                <span className="preview-value">{currentData.extraction_stage?.toFixed(2)}%</span>
                <CGWBBadge category={currentData.cgwb_category} size="sm" />
              </div>
            )}
            {currentData.gw_extraction !== null && currentData.gw_extraction !== undefined && (
              <div className="preview-item">
                <span className="preview-label">Total GW Extraction</span>
                <span className="preview-value">{currentData.gw_extraction?.toFixed(2)} ham</span>
              </div>
            )}
            {currentData.annual_extractable !== null && currentData.annual_extractable !== undefined && (
              <div className="preview-item">
                <span className="preview-label">Total Annual Extractable</span>
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
              📋 Total-extraction mathematical simulation based on INGRES/CGWB assessment data ({result.assessment_year}).
              For PQ-zone districts, official CGWB stage (C+NC) may differ from this total-extraction calculation.
              No database records were modified.
            </div>
          </div>

          {/* Reset Button */}
          <button className="reset-btn" onClick={() => { setResult(null); setError(''); }}>
            🔄 Reset Uniform Simulation
          </button>
        </div>
      )}

      {/* Multi-Sector Intervention & Scenario Comparison */}
      {selectedState && selectedDistrict && (
        <div className="multisector-section">
          <div className="multisector-header">
            <h3>🧩 Multi-Sector Intervention Scenario Comparison</h3>
            <p>
              Simulate independent percentage changes across Irrigation, Domestic, and Industrial extraction.
              Outputs separate Official CGWB (C+NC) stage from Total-extraction stage and label estimates clearly.
            </p>
          </div>

          <div className="sector-sliders-grid">
            <div className="sector-slider-card">
              <label className="control-label">🌾 Irrigation Change: <strong>{irrPct}%</strong></label>
              <input
                type="range" min="-100" max="100" step="1"
                value={irrPct} onChange={e => setIrrPct(Number(e.target.value))}
                className="whatif-slider"
              />
              <div className="slider-value-row">
                <input type="number" min="-100" max="200" value={irrPct} onChange={e => setIrrPct(Number(e.target.value))} className="pct-input" />
                <span className="pct-unit">%</span>
              </div>
            </div>

            <div className="sector-slider-card">
              <label className="control-label">🏠 Domestic Change: <strong>{domPct}%</strong></label>
              <input
                type="range" min="-100" max="100" step="1"
                value={domPct} onChange={e => setDomPct(Number(e.target.value))}
                className="whatif-slider"
              />
              <div className="slider-value-row">
                <input type="number" min="-100" max="200" value={domPct} onChange={e => setDomPct(Number(e.target.value))} className="pct-input" />
                <span className="pct-unit">%</span>
              </div>
            </div>

            <div className="sector-slider-card">
              <label className="control-label">🏭 Industrial Change: <strong>{indPct}%</strong></label>
              <input
                type="range" min="-100" max="100" step="1"
                value={indPct} onChange={e => setIndPct(Number(e.target.value))}
                className="whatif-slider"
              />
              <div className="slider-value-row">
                <input type="number" min="-100" max="200" value={indPct} onChange={e => setIndPct(Number(e.target.value))} className="pct-input" />
                <span className="pct-unit">%</span>
              </div>
            </div>
          </div>

          <div className="scenario-builder-bar">
            <input
              type="text"
              className="whatif-select scenario-name-input"
              value={scenarioName}
              onChange={e => setScenarioName(e.target.value)}
              placeholder="Scenario name..."
            />
            <button type="button" className="secondary-action-btn" onClick={handleAddCustomScenario}>
              ➕ Add Scenario to Comparison
            </button>
            <button type="button" className="reset-btn inline-reset" onClick={() => setScenarioQueue(PRESET_SCENARIOS)}>
              ↺ Reset to Presets (A / B / C)
            </button>
          </div>

          {/* Active Scenario Queue */}
          <div className="scenario-queue">
            {scenarioQueue.map((sc, idx) => (
              <div key={idx} className="scenario-chip">
                <span>
                  <strong>{sc.name}</strong> (Irr {sc.irrigation_pct_change}%, Dom {sc.domestic_pct_change}%, Ind {sc.industrial_pct_change}%)
                </span>
                <button type="button" className="chip-remove" onClick={() => handleRemoveScenario(idx)} title="Remove">×</button>
              </div>
            ))}
          </div>

          <button
            className="calculate-btn"
            onClick={handleRunMultiScenario}
            disabled={multiLoading || scenarioQueue.length === 0}
          >
            {multiLoading ? (
              <><span className="btn-spinner" /> Comparing Scenarios...</>
            ) : (
              '📊 Compare Multi-Sector Scenarios'
            )}
          </button>

          {multiError && <div className="whatif-error" style={{ marginTop: 14 }}>⚠️ {multiError}</div>}

          {multiResult && (
            <div className="multisector-results">
              {multiResult.official_cgwb_metrics?.has_pq_zone && (
                <div className="pq-warning-banner">
                  ⚠️ <strong>PQ-Zone District:</strong> {multiResult.official_cgwb_metrics.pq_note}{' '}
                  Official C+NC Baseline: <strong>{multiResult.official_cgwb_metrics.reported_official_stage_pct?.toFixed(2)}%</strong> vs.
                  Total Baseline: <strong>{multiResult.official_cgwb_metrics.total_based_stage_pct?.toFixed(2)}%</strong>.
                </div>
              )}

              <div className="scenario-disclaimer-banner">
                📐 <strong>Mathematical Scenario Comparison:</strong> Outputs are mathematical calculations from
                INGRES 2024–2025 sector extraction data and do not validate field feasibility (MI Census / crop / piezometer data missing).
              </div>

              <div className="scenario-table-wrap">
                <table className="diag-table">
                  <thead>
                    <tr>
                      <th>Scenario</th>
                      <th>Calculation Basis</th>
                      <th>Revised Sectors (Irr / Dom / Ind ham)</th>
                      <th>Simulated Official Stage (C+NC)</th>
                      <th>Simulated Total Stage</th>
                      <th>Reduction vs. Baseline</th>
                      <th>Remaining to Safe (&le;70%)</th>
                      <th>Reaches Safe?</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(multiResult.scenarios || []).map((sc, i) => (
                      <tr key={i}>
                        <td>
                          <strong>{sc.name}</strong>
                          <div className="scenario-inputs-sub">{sc.assumption_note}</div>
                        </td>
                        <td>
                          <span className={`basis-badge ${sc.simulation_basis === 'EXACT_CGWB_C_NC' ? 'basis-exact' : 'basis-estimate'}`}>
                            {sc.simulation_basis === 'EXACT_CGWB_C_NC' ? 'Exact C+NC Basis' : 'Estimate Only'}
                          </span>
                          <div className="scenario-inputs-sub">{sc.practical_feasibility_label}</div>
                        </td>
                        <td>
                          {sc.revised_sector_total_ham?.irrigation?.toFixed(1) ?? '—'} /{' '}
                          {sc.revised_sector_total_ham?.domestic?.toFixed(1) ?? '—'} /{' '}
                          {sc.revised_sector_total_ham?.industrial?.toFixed(1) ?? '—'}
                        </td>
                        <td>
                          {sc.simulated_official_stage_pct !== null && sc.simulated_official_stage_pct !== undefined
                            ? `${sc.simulated_official_stage_pct.toFixed(2)}%`
                            : 'N/A'}
                          {sc.simulated_official_category?.category && (
                            <div><CGWBBadge category={sc.simulated_official_category.category} size="sm" /></div>
                          )}
                        </td>
                        <td>
                          {sc.simulated_total_stage_pct !== null && sc.simulated_total_stage_pct !== undefined
                            ? `${sc.simulated_total_stage_pct.toFixed(2)}%`
                            : 'N/A'}
                        </td>
                        <td>
                          {sc.reduction_achieved_ham !== null && sc.reduction_achieved_ham !== undefined
                            ? `${sc.reduction_achieved_ham.toFixed(2)} ham (${sc.reduction_achieved_pct?.toFixed(1)}%)`
                            : 'N/A'}
                        </td>
                        <td>
                          {sc.remaining_reduction_to_safe_ham !== null && sc.remaining_reduction_to_safe_ham !== undefined
                            ? `${sc.remaining_reduction_to_safe_ham.toFixed(2)} ham`
                            : 'N/A'}
                        </td>
                        <td>
                          <span className={`safe-pill ${sc.reaches_safe ? 'safe-yes' : 'safe-no'}`}>
                            {sc.reaches_safe ? 'Yes' : 'No'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
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
