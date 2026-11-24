import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, ReferenceLine
} from 'recharts';

const CGWB_COLORS = {
  'SAFE':           '#10b981',
  'SEMI-CRITICAL':  '#f59e0b',
  'CRITICAL':       '#f97316',
  'OVER-EXPLOITED': '#ef4444',
};

const DEFAULT_COLORS = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a'];

const getExtractionColor = (stage) => {
  if (!stage && stage !== 0) return '#667eea';
  if (stage <= 70)  return '#10b981';
  if (stage <= 90)  return '#f59e0b';
  if (stage <= 100) return '#f97316';
  return '#ef4444';
};

/**
 * Custom tooltip for extraction charts — shows category alongside value.
 */
const ExtractionTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const val = payload[0].value;
  return (
    <div className="custom-tooltip">
      <p className="tooltip-label">{label}</p>
      <p className="tooltip-value">{val?.toFixed(2)}%</p>
    </div>
  );
};

const ChartDisplay = ({ chartData }) => {
  if (!chartData || !chartData.type) return null;

  const { type } = chartData;

  // ── Rainfall bar chart ────────────────────────────────────────────────────
  if (type === 'rainfall') {
    const data = chartData.data || [];
    return (
      <div className="chart-container">
        <h4>🌧️ Rainfall Distribution (mm)</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 80 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="district" angle={-40} textAnchor="end" height={90} tick={{ fontSize: 11 }} />
            <YAxis label={{ value: 'mm', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(v) => `${v?.toFixed(2)} mm`} />
            <Bar dataKey="rainfall" name="Rainfall (mm)" radius={[4, 4, 0, 0]}>
              {data.map((_, idx) => (
                <Cell key={idx} fill={DEFAULT_COLORS[idx % DEFAULT_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Extraction stage bar chart ────────────────────────────────────────────
  if (type === 'extraction') {
    const data = chartData.data || [];
    return (
      <div className="chart-container">
        <h4>📊 Stage of Groundwater Extraction (%)</h4>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data} margin={{ top: 20, right: 30, left: 10, bottom: 80 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="district" angle={-40} textAnchor="end" height={90} tick={{ fontSize: 11 }} />
            <YAxis
              label={{ value: '%', angle: -90, position: 'insideLeft' }}
              domain={[0, (dataMax) => Math.max(dataMax * 1.1, 110)]}
            />
            <Tooltip content={<ExtractionTooltip />} />
            <ReferenceLine y={70}  stroke="#10b981" strokeDasharray="5 5" label={{ value: 'Safe 70%',     position: 'right', fontSize: 11, fill: '#10b981' }} />
            <ReferenceLine y={90}  stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Semi-Crit 90%', position: 'right', fontSize: 11, fill: '#f59e0b' }} />
            <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Critical 100%',  position: 'right', fontSize: 11, fill: '#ef4444' }} />
            <Bar dataKey="extraction" name="Stage (%)" radius={[4, 4, 0, 0]}>
              {data.map((entry, idx) => (
                <Cell key={idx} fill={getExtractionColor(entry.extraction)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {/* CGWB Legend */}
        <div className="chart-legend">
          <span style={{ color: '#10b981' }}>🟢 Safe ≤70%</span>
          <span style={{ color: '#f59e0b' }}>🟡 Semi-Critical 70–90%</span>
          <span style={{ color: '#f97316' }}>🟠 Critical 90–100%</span>
          <span style={{ color: '#ef4444' }}>🔴 Over-Exploited &gt;100%</span>
        </div>
      </div>
    );
  }

  // ── Comparison chart (dual-axis: rainfall + extraction separate) ──────────
  if (type === 'comparison') {
    const data = chartData.data || [];
    return (
      <div className="chart-container">
        <h4>📊 Groundwater Comparison</h4>
        {/* Rainfall */}
        <p className="chart-subtitle">🌧️ Rainfall (mm)</p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip formatter={(v) => `${v?.toFixed(2)} mm`} />
            <Bar dataKey="rainfall" name="Rainfall (mm)" fill="#667eea" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {/* Extraction */}
        <p className="chart-subtitle" style={{ marginTop: '12px' }}>📊 Extraction Stage (%)</p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis domain={[0, (m) => Math.max(m * 1.1, 110)]} />
            <Tooltip formatter={(v) => `${v?.toFixed(2)}%`} />
            <ReferenceLine y={70}  stroke="#10b981" strokeDasharray="5 5" />
            <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="5 5" />
            <Bar dataKey="extraction" name="Extraction (%)" radius={[4, 4, 0, 0]}>
              {data.map((entry, idx) => (
                <Cell key={idx} fill={getExtractionColor(entry.extraction)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── State overview: separate rainfall + extraction bars + CGWB donut ──────
  if (type === 'state_overview') {
    const rainfallData   = chartData.rainfall_data   || [];
    const extractionData = chartData.extraction_data || [];
    const cgwbData       = chartData.cgwb_distribution || [];

    return (
      <div className="chart-container">
        {/* Rainfall bar */}
        {rainfallData.length > 0 && (
          <>
            <h4>🌧️ Rainfall by District (mm)</h4>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rainfallData} margin={{ top: 10, right: 20, left: 10, bottom: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="district" angle={-40} textAnchor="end" height={90} tick={{ fontSize: 11 }} />
                <YAxis label={{ value: 'mm', angle: -90, position: 'insideLeft' }} />
                <Tooltip formatter={(v) => `${v?.toFixed(2)} mm`} />
                <Bar dataKey="rainfall" name="Rainfall (mm)" fill="#667eea" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        {/* Extraction stage bar */}
        {extractionData.length > 0 && (
          <>
            <h4 style={{ marginTop: '20px' }}>📊 Extraction Stage by District (%)</h4>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={extractionData} margin={{ top: 20, right: 30, left: 10, bottom: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="district" angle={-40} textAnchor="end" height={90} tick={{ fontSize: 11 }} />
                <YAxis
                  label={{ value: '%', angle: -90, position: 'insideLeft' }}
                  domain={[0, (m) => Math.max(m * 1.1, 110)]}
                />
                <Tooltip content={<ExtractionTooltip />} />
                <ReferenceLine y={70}  stroke="#10b981" strokeDasharray="5 5" label={{ value: '70%', position: 'right', fontSize: 11, fill: '#10b981' }} />
                <ReferenceLine y={90}  stroke="#f59e0b" strokeDasharray="5 5" label={{ value: '90%', position: 'right', fontSize: 11, fill: '#f59e0b' }} />
                <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="5 5" label={{ value: '100%', position: 'right', fontSize: 11, fill: '#ef4444' }} />
                <Bar dataKey="extraction" name="Stage (%)" radius={[4, 4, 0, 0]}>
                  {extractionData.map((entry, idx) => (
                    <Cell key={idx} fill={getExtractionColor(entry.extraction)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        {/* CGWB category donut */}
        {cgwbData.length > 0 && (
          <>
            <h4 style={{ marginTop: '20px' }}>🏷️ CGWB Category Distribution</h4>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={cgwbData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {cgwbData.map((entry, idx) => (
                    <Cell key={idx} fill={CGWB_COLORS[entry.name] || DEFAULT_COLORS[idx]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </>
        )}
      </div>
    );
  }

  // ── CGWB distribution donut (standalone) ─────────────────────────────────
  if (type === 'cgwb_distribution') {
    const data = chartData.data || [];
    return (
      <div className="chart-container">
        <h4>🏷️ CGWB Category Distribution</h4>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={3}
              dataKey="value"
              label={({ name, value }) => `${name}: ${value}`}
            >
              {data.map((entry, idx) => (
                <Cell key={idx} fill={CGWB_COLORS[entry.name] || DEFAULT_COLORS[idx]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── What-If comparison bar ────────────────────────────────────────────────
  if (type === 'whatif_comparison') {
    const data       = chartData.data       || [];
    const thresholds = chartData.thresholds || { safe: 70, semi_critical: 90, critical: 100 };
    const maxStage   = Math.max(...data.map(d => d.stage || 0)) * 1.2;

    return (
      <div className="chart-container">
        <h4>📊 What-If: Before vs After Simulation</h4>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 20, right: 50, left: 20, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis
              label={{ value: 'Stage (%)', angle: -90, position: 'insideLeft' }}
              domain={[0, Math.max(maxStage, 110)]}
            />
            <Tooltip formatter={(v) => `${v?.toFixed(2)}%`} />
            <ReferenceLine y={thresholds.safe}         stroke="#10b981" strokeDasharray="5 5" label={{ value: 'Safe 70%',       position: 'right', fontSize: 11, fill: '#10b981' }} />
            <ReferenceLine y={thresholds.semi_critical} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Semi-Crit 90%', position: 'right', fontSize: 11, fill: '#f59e0b' }} />
            <ReferenceLine y={thresholds.critical}     stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Critical 100%',  position: 'right', fontSize: 11, fill: '#ef4444' }} />
            <Bar dataKey="stage" name="Stage (%)" radius={[6, 6, 0, 0]}>
              {data.map((entry, idx) => (
                <Cell key={idx} fill={getExtractionColor(entry.stage)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
};

export default ChartDisplay;
