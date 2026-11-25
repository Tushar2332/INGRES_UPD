import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from 'recharts';
import CGWBBadge from './CGWBBadge';
import VerificationBadge from './VerificationBadge';
import DataSourceTag from './DataSourceTag';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TAG_META = {
  VERIFIED_FACT:         { label: 'VERIFIED FACT',         cls: 'tag-verified' },
  DERIVED_CALCULATION:   { label: 'DERIVED CALCULATION',   cls: 'tag-derived' },
  HYPOTHESIS_UNVERIFIED: { label: 'UNVERIFIED HYPOTHESIS', cls: 'tag-hypothesis' },
  DATA_MISSING:          { label: 'DATA MISSING',          cls: 'tag-missing' },
  RECOMMENDATION:        { label: 'RECOMMENDATION',        cls: 'tag-recommendation' },
};

const GAP_LABELS = {
  well_and_borewell_counts:           'Well & Borewell Counts (MI Census)',
  pump_types_and_energy_sources:      'Pump Types & Energy Sources (Electric / Diesel / Solar)',
  drip_and_sprinkler_adoption:        'Drip & Sprinkler Micro-Irrigation Adoption',
  crop_area_and_water_requirements:   'Crop-Level Area & Water Requirements',
  agricultural_electricity_consumption: 'Agricultural Electricity & Feeder Consumption',
  groundwater_level_decline_trend:    'Multi-Year Groundwater Level Decline (Piezometer m bgl)',
  naquim_aquifer_hydrogeology:        'NAQUIM Aquifer Lithology & Specific Yield',
  water_quality_tagging:              'Groundwater Quality Tagging (0/726 in workbook)',
  sub_district_assessment_units:      'Sub-District Assessment Units (Block / Taluk / Mandal)',
};

const SECTOR_COLORS = {
  Irrigation: '#059669',
  Domestic:   '#3b82f6',
  Industrial: '#8b5cf6',
};

const formatTitle = (s) =>
  s ? s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : '';

const StatementList = ({ items = [] }) => {
  if (!items || items.length === 0) return null;
  return (
    <div className="diag-statements">
      {items.map((item, idx) => {
        const meta = TAG_META[item.classification] || {
          label: item.classification,
          cls: 'tag-derived',
        };
        return (
          <div key={idx} className={`diag-statement-row ${meta.cls}-border`}>
            <span className={`epistemic-tag ${meta.cls}`}>{meta.label}</span>
            <div className="diag-statement-body">
              <p>{item.text}</p>
              {item.assumption && (
                <div className="diag-assumption">Assumption: {item.assumption}</div>
              )}
              {item.evidence_refs && item.evidence_refs.length > 0 && (
                <div className="diag-refs">
                  Fields: {item.evidence_refs.join(', ')}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

/**
 * DiagnosticPanel — Evidence-based Groundwater Diagnostic & Recommendation Module.
 */
const DiagnosticPanel = ({ externalTarget, onOpenWhatIf }) => {
  const [states, setStates]                   = useState([]);
  const [districts, setDistricts]             = useState([]);
  const [selectedState, setSelectedState]     = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [pendingDistrict, setPendingDistrict] = useState('');
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [loading, setLoading]                 = useState(false);
  const [error, setError]                     = useState('');
  const [diagnostic, setDiagnostic]           = useState(null);

  useEffect(() => {
    axios.get(`${API_URL}/states`)
      .then((r) => setStates(r.data))
      .catch(() => setError('Could not load states list from backend.'));
  }, []);

  useEffect(() => {
    if (!selectedState) {
      setDistricts([]);
      return;
    }
    setLoadingDistricts(true);
    setDistricts([]);
    axios.get(`${API_URL}/districts/${encodeURIComponent(selectedState)}`)
      .then((r) => {
        setDistricts(r.data);
        setLoadingDistricts(false);
      })
      .catch(() => {
        setError('Could not load districts.');
        setLoadingDistricts(false);
      });
  }, [selectedState]);

  const runDiagnosis = useCallback(async (st, dt) => {
    if (!st || !dt) {
      setError('Please select a state and district first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await axios.post(`${API_URL}/diagnose`, {
        state: st,
        district: dt,
      });
      setDiagnostic(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Diagnostic analysis failed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Accept handoff from WhatIfPanel
  useEffect(() => {
    if (externalTarget && externalTarget.state && externalTarget.district) {
      setSelectedState(externalTarget.state);
      setPendingDistrict(externalTarget.district);
    }
  }, [externalTarget]);

  // Once districts load for pending external handoff, select and run diagnosis
  useEffect(() => {
    if (pendingDistrict && districts.length > 0) {
      const match = districts.find(
        (d) => d.toUpperCase() === pendingDistrict.toUpperCase()
      );
      if (match) {
        setSelectedDistrict(match);
        setPendingDistrict('');
        runDiagnosis(selectedState, match);
      }
    }
  }, [pendingDistrict, districts, selectedState, runDiagnosis]);

  const off = diagnostic?.current_condition?.official_cgwb;
  const tot = diagnostic?.current_condition?.total_summary;
  const reqImp = diagnostic?.required_improvement;
  const maj = diagnostic?.major_contributors;
  const scenarios = diagnostic?.expected_impact?.scenarios || [];

  const sectorChartData = (maj?.sectors || []).map((s) => ({
    sector: s.sector,
    total_ham: s.total_ham ?? 0,
    fresh_cnc_ham: s.fresh_cnc_ham ?? 0,
    share_of_total_pct: s.share_of_total_pct ?? 0,
  }));

  return (
    <div className="diagnostic-panel">
      <div className="whatif-header">
        <h2>🩺 Groundwater Diagnostic &amp; Improvement Module</h2>
        <p>
          Evidence-based assessment connecting 2024–2025 CGWB sector records, Safe-threshold targets,
          mathematical intervention scenarios, and explicit data gaps.
        </p>
      </div>

      {/* Location Selection */}
      <div className="whatif-controls">
        <div className="control-group">
          <label className="control-label">📍 State</label>
          <select
            className="whatif-select"
            value={selectedState}
            onChange={(e) => {
              setSelectedState(e.target.value);
              setSelectedDistrict('');
              setDiagnostic(null);
              setError('');
            }}
          >
            <option value="">— Select State —</option>
            {states.map((s) => (
              <option key={s} value={s}>{formatTitle(s)}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label className="control-label">🏘️ District</label>
          <select
            className="whatif-select"
            value={selectedDistrict}
            onChange={(e) => setSelectedDistrict(e.target.value)}
            disabled={!selectedState || loadingDistricts}
          >
            <option value="">— Select District —</option>
            {districts.map((d) => (
              <option key={d} value={d}>{formatTitle(d)}</option>
            ))}
          </select>
          {loadingDistricts && <span className="loading-hint">Loading districts...</span>}
        </div>

        <button
          className="calculate-btn"
          onClick={() => runDiagnosis(selectedState, selectedDistrict)}
          disabled={loading || !selectedState || !selectedDistrict}
        >
          {loading ? (
            <><span className="btn-spinner" /> Running Evidence Diagnosis...</>
          ) : (
            '🔍 Run Groundwater Diagnosis'
          )}
        </button>
      </div>

      {error && <div className="whatif-error">⚠️ {error}</div>}

      {!diagnostic && !loading && (
        <div className="whatif-instructions">
          <h4>What This Module Evaluates</h4>
          <ol>
            <li><strong>Current Groundwater Condition:</strong> Official CGWB Freshwater (C + NC) status vs. Total (C + NC + PQ) extraction.</li>
            <li><strong>Sectoral Contributors:</strong> Irrigation, Domestic, and Industrial groundwater draft and recharge sources.</li>
            <li><strong>Safe-Target Gap:</strong> Exact extraction reduction needed to reach CGWB Safe (&le;70%).</li>
            <li><strong>Evidence-Gated Interventions &amp; Scenarios:</strong> Practical options supported by local records plus multi-sector math scenarios.</li>
            <li><strong>Honest Data Gaps:</strong> Explicitly marks missing MI Census, electricity, crop, hydrogeology, and piezometer water-level datasets as <code>DATA_MISSING</code>.</li>
          </ol>
        </div>
      )}

      {diagnostic && (
        <div className="diag-results">
          {/* Header Meta Bar */}
          <div className="diag-meta-bar">
            <div>
              <h3>
                {formatTitle(diagnostic.location?.district)}, {formatTitle(diagnostic.location?.state)}
              </h3>
              <span className="diag-geo-pill">
                Resolution: {diagnostic.location?.geo_resolution || 'district'}
              </span>
            </div>
            <div className="diag-meta-actions">
              <VerificationBadge
                verified={diagnostic.verified}
                issues={diagnostic.verification_issues || []}
              />
              {onOpenWhatIf && (
                <button
                  className="secondary-action-btn"
                  onClick={() => onOpenWhatIf(diagnostic.location?.state, diagnostic.location?.district)}
                >
                  🔬 Simulate Custom Sectors in What-If
                </button>
              )}
            </div>
          </div>

          {/* 1. Official CGWB vs Total Extraction Summary */}
          <section className="diag-section">
            <h4>1. Current Groundwater Condition (Official CGWB vs. Total Extraction)</h4>
            <div className="diag-kpi-grid">
              <div className="diag-kpi-card highlight-official">
                <div className="kpi-title">Official CGWB Stage (C + NC Freshwater)</div>
                <div className="kpi-value">
                  {reqImp?.current_official_stage_pct !== null && reqImp?.current_official_stage_pct !== undefined
                    ? `${reqImp.current_official_stage_pct.toFixed(2)}%`
                    : 'N/A'}
                </div>
                <CGWBBadge
                  category={off?.official_category?.category}
                  stage={reqImp?.current_official_stage_pct}
                  size="sm"
                />
                <div className="kpi-sub">
                  C+NC Extraction: {off?.fresh_extraction_ham?.toFixed(2) ?? 'N/A'} ham / Extractable: {off?.fresh_extractable_ham?.toFixed(2) ?? 'N/A'} ham
                </div>
              </div>

              <div className="diag-kpi-card">
                <div className="kpi-title">Total Extraction Stage (C + NC + PQ)</div>
                <div className="kpi-value">
                  {off?.total_based_stage_pct !== null && off?.total_based_stage_pct !== undefined
                    ? `${off.total_based_stage_pct.toFixed(2)}%`
                    : 'N/A'}
                </div>
                <div className="kpi-sub">
                  Total Extraction: {tot?.gw_extraction_ham?.toFixed(2) ?? 'N/A'} ham / Extractable: {tot?.annual_extractable_gw_resource_ham?.toFixed(2) ?? 'N/A'} ham
                </div>
                <div className="kpi-sub">
                  Net Future Avail.: {tot?.net_gw_availability_ham?.toFixed(2) ?? 'N/A'} ham · Rainfall: {tot?.rainfall_mm?.toFixed(1) ?? 'N/A'} mm
                </div>
              </div>

              <div className="diag-kpi-card">
                <div className="kpi-title">2. Required Reduction to Safe (&le;70% Official)</div>
                <div className={`kpi-value ${reqImp?.already_safe ? 'text-safe' : 'text-stress'}`}>
                  {reqImp?.already_safe
                    ? '0.00 ham (Already Safe)'
                    : reqImp?.required_reduction_ham !== null && reqImp?.required_reduction_ham !== undefined
                      ? `-${reqImp.required_reduction_ham.toFixed(2)} ham (${reqImp.required_reduction_pct?.toFixed(1)}%)`
                      : 'N/A'}
                </div>
                <div className="kpi-sub">
                  Target Official Ceiling: {reqImp?.target_safe_extraction_ham?.toFixed(2) ?? 'N/A'} ham
                </div>
                <div className="kpi-sub">
                  Env. Flows: {tot?.env_flows_ham?.toFixed(2) ?? 'N/A'} ham · 2025 Dom Alloc: {tot?.domestic_alloc_2025_ham?.toFixed(2) ?? 'N/A'} ham
                </div>
              </div>
            </div>

            {off?.has_pq_zone && (
              <div className="pq-warning-banner">
                ⚠️ <strong>Poor Quality (PQ) Zone Notice:</strong> {off.pq_note} (PQ Extractable: {off.extractable_pq_ham?.toFixed(2)} ham, PQ Extraction: {off.extraction_pq_ham?.toFixed(2)} ham).
              </div>
            )}

            <StatementList items={diagnostic.current_condition?.statements} />
            <StatementList items={reqImp?.statements} />
          </section>

          {/* 2. Major Sectoral Contributors & Recharge Sources */}
          <section className="diag-section">
            <h4>3. Major Groundwater Contributors &amp; Recharge Sources</h4>
            <div className="diag-split-grid">
              <div className="diag-chart-box">
                <h5>Sectoral Extraction (ham) — Dominant: {maj?.dominant_sector || 'N/A'}</h5>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={sectorChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="sector" />
                    <YAxis />
                    <Tooltip formatter={(v) => `${Number(v).toFixed(2)} ham`} />
                    <Bar dataKey="total_ham" name="Total Extraction (ham)" radius={[6, 6, 0, 0]}>
                      {sectorChartData.map((entry, idx) => (
                        <Cell key={idx} fill={SECTOR_COLORS[entry.sector] || '#667eea'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="sector-pills">
                  {(maj?.sectors || []).map((s) => (
                    <span key={s.sector} className="sector-pill">
                      <strong>{s.sector}:</strong> {s.total_ham?.toFixed(2) ?? 'N/A'} ham ({s.share_of_total_pct?.toFixed(1) ?? 'N/A'}%)
                    </span>
                  ))}
                </div>
              </div>

              <div className="diag-recharge-box">
                <h5>Recharge Sources (Annual Recharge: {tot?.ground_water_recharge_ham?.toFixed(2) ?? 'N/A'} ham)</h5>
                <table className="diag-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Amount (ham)</th>
                      <th>Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(maj?.recharge_sources || []).map((r) => (
                      <tr key={r.source}>
                        <td>{r.source}</td>
                        <td>{r.amount_ham !== null && r.amount_ham !== undefined ? r.amount_ham.toFixed(2) : 'N/A'}</td>
                        <td>{r.share_pct !== null && r.share_pct !== undefined ? `${r.share_pct.toFixed(1)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <StatementList items={maj?.statements} />
          </section>

          {/* 3. Recommended Interventions */}
          <section className="diag-section">
            <h4>4. Evidence-Supported Candidate Interventions</h4>
            {diagnostic.recommended_interventions?.length === 0 ? (
              <p className="diag-empty">No stress-driven interventions triggered for current records.</p>
            ) : (
              <div className="interventions-grid">
                {diagnostic.recommended_interventions.map((item) => (
                  <div key={item.id} className="intervention-card">
                    <div className="intervention-header">
                      <span className="epistemic-tag tag-recommendation">{item.classification}</span>
                      <span className={`relevance-pill rel-${item.relevance}`}>
                        {item.relevance.toUpperCase()} RELEVANCE · {item.sector}
                      </span>
                    </div>
                    <h5>{item.title}</h5>
                    <p className="intervention-rationale">{item.rationale}</p>

                    {item.supporting_evidence?.length > 0 && (
                      <div className="intervention-subblock">
                        <strong>Supporting Local Evidence:</strong>
                        <ul>
                          {item.supporting_evidence.map((ev, i) => <li key={i}>{ev}</li>)}
                        </ul>
                      </div>
                    )}

                    {item.required_feasibility_data?.length > 0 && (
                      <div className="intervention-subblock">
                        <strong>Additional Data Needed to Confirm Feasibility:</strong>
                        <ul>
                          {item.required_feasibility_data.map((req, i) => <li key={i}>{req}</li>)}
                        </ul>
                      </div>
                    )}

                    {item.caveats?.length > 0 && (
                      <div className="intervention-caveats">
                        <strong>Caveats:</strong>
                        <ul>
                          {item.caveats.map((cav, i) => <li key={i}>{cav}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 4. Mathematical Scenario Outcomes */}
          <section className="diag-section">
            <h4>5. Expected Impact — Mathematical Sector Scenarios</h4>
            <div className="scenario-disclaimer-banner">
              📐 <strong>Mathematical Scenario Notice:</strong> Calculations below evaluate theoretical stage
              outcomes from percentage extraction changes. They do <strong>not</strong> imply real-world
              achievability without MI Census, crop, energy, and aquifer feasibility checks.
            </div>
            <div className="scenario-table-wrap">
              <table className="diag-table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Basis &amp; Status</th>
                    <th>Simulated Official Stage (C+NC)</th>
                    <th>Simulated Total Stage</th>
                    <th>Reduction Achieved</th>
                    <th>Remaining to Safe</th>
                    <th>Reaches Safe?</th>
                  </tr>
                </thead>
                <tbody>
                  {scenarios.map((sc, idx) => (
                    <tr key={idx}>
                      <td>
                        <strong>{sc.name}</strong>
                        <div className="scenario-inputs-sub">
                          Irr {sc.inputs.irrigation_pct_change}% · Dom {sc.inputs.domestic_pct_change}% · Ind {sc.inputs.industrial_pct_change}%
                        </div>
                      </td>
                      <td>
                        <span className={`basis-badge ${sc.simulation_basis === 'EXACT_CGWB_C_NC' ? 'basis-exact' : 'basis-estimate'}`}>
                          {sc.simulation_basis === 'EXACT_CGWB_C_NC' ? 'Exact C+NC Basis' : 'Estimate Only'}
                        </span>
                        <div className="scenario-inputs-sub">{sc.practical_feasibility_label}</div>
                      </td>
                      <td>
                        {sc.simulated_official_stage_pct !== null && sc.simulated_official_stage_pct !== undefined
                          ? `${sc.simulated_official_stage_pct.toFixed(2)}%`
                          : 'N/A'}
                        {sc.simulated_official_category?.category && (
                          <div>
                            <CGWBBadge category={sc.simulated_official_category.category} size="sm" />
                          </div>
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
                          {sc.reaches_safe ? 'Yes (<=70%)' : 'No'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <StatementList items={diagnostic.expected_impact?.statements} />
          </section>

          {/* 5. Evidence Registry & Unverified Hypotheses */}
          <section className="diag-section">
            <h4>6. Tagged Evidence &amp; Unverified Hypotheses</h4>
            <StatementList items={diagnostic.evidence} />
          </section>

          {/* 6. Missing Data & Limitations */}
          <section className="diag-section">
            <h4>7. Unavailable Data (DATA_MISSING) &amp; Limitations</h4>
            <div className="data-gaps-grid">
              {Object.entries(diagnostic.data_gaps_summary || {}).map(([k, status]) => (
                <div key={k} className="data-gap-chip">
                  <span className="epistemic-tag tag-missing">{status}</span>
                  <span>{GAP_LABELS[k] || k}</span>
                </div>
              ))}
            </div>
            <StatementList items={diagnostic.limitations} />
          </section>

          {/* 7. Next Steps */}
          <section className="diag-section">
            <h4>8. Recommended Next Steps for Local Verification</h4>
            <StatementList items={diagnostic.next_steps} />
          </section>

          <DataSourceTag
            assessmentYear={diagnostic.location?.assessment_year}
            dataSource={diagnostic.location?.data_source}
            dataConfidence="District-Level INGRES Assessment (No External MI Census / Piezometer Data Loaded)"
          />
        </div>
      )}
    </div>
  );
};

export default DiagnosticPanel;
