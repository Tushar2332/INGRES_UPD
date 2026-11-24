import React from 'react';
import CGWBBadge from './CGWBBadge';

/**
 * DataCard — displays a groundwater data record card.
 * Now includes CGWB category badge, assessment year, and data source.
 */
const DataCard = ({ data }) => {
  const extractionColor = () => {
    const s = data.extraction_stage;
    if (s === null || s === undefined) return '#64748b';
    if (s <= 70)  return '#10b981';
    if (s <= 90)  return '#f59e0b';
    if (s <= 100) return '#f97316';
    return '#ef4444';
  };

  const districtName = data.district
    ? data.district.charAt(0) + data.district.slice(1).toLowerCase()
    : '—';
  const stateName = data.state
    ? data.state.charAt(0) + data.state.slice(1).toLowerCase()
    : '—';

  return (
    <div className="data-card">
      <div className="card-header">
        <h3>{districtName}</h3>
        <span className="state-badge">{stateName}</span>
      </div>

      <div className="card-body">
        {data.rainfall !== null && data.rainfall !== undefined && (
          <div className="data-item">
            <span className="data-label">🌧️ Rainfall</span>
            <span className="data-value">{data.rainfall} mm</span>
          </div>
        )}

        {data.extraction_stage !== null && data.extraction_stage !== undefined && (
          <div className="data-item">
            <span className="data-label">📊 Extraction Stage</span>
            <span className="data-value" style={{ color: extractionColor() }}>
              {data.extraction_stage}%
            </span>
          </div>
        )}

        {data.cgwb_category && (
          <div className="data-item">
            <span className="data-label">🏷️ CGWB Category</span>
            <CGWBBadge category={data.cgwb_category} stage={data.extraction_stage} size="sm" />
          </div>
        )}

        {data.gw_recharge !== null && data.gw_recharge !== undefined && (
          <div className="data-item">
            <span className="data-label">♻️ GW Recharge</span>
            <span className="data-value">{data.gw_recharge} ham</span>
          </div>
        )}

        {data.net_availability !== null && data.net_availability !== undefined && (
          <div className="data-item">
            <span className="data-label">💦 Net Availability</span>
            <span className="data-value">{data.net_availability} ham</span>
          </div>
        )}
      </div>

      {/* Footer: source + year */}
      {(data.assessment_year || data.data_source) && (
        <div className="card-footer">
          {data.data_source && (
            <span className="card-source">📁 {data.data_source}</span>
          )}
          {data.assessment_year && (
            <span className="card-year">📅 {data.assessment_year}</span>
          )}
        </div>
      )}
    </div>
  );
};

export default DataCard;
