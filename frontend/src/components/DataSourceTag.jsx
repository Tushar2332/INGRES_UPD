import React from 'react';

/**
 * DataSourceTag — displays source, assessment year, and data confidence tag.
 *
 * Props:
 *   assessmentYear: string   — e.g. "2022"
 *   dataSource:     string   — e.g. "INGRES / CGWB (GEC-2022)"
 *   dataConfidence: string   — e.g. "Latest Available Assessment"
 */
const DataSourceTag = ({ assessmentYear, dataSource, dataConfidence }) => {
  if (!assessmentYear && !dataSource) return null;

  return (
    <div className="data-source-tag">
      {dataSource && (
        <span className="source-item" title="Data Source">
          📁 {dataSource}
        </span>
      )}
      {assessmentYear && (
        <span className="source-item" title="Assessment Year">
          📅 Assessment Year: {assessmentYear}
        </span>
      )}
      {dataConfidence && (
        <span className="source-item confidence-tag" title="Data Confidence">
          🏷️ {dataConfidence}
        </span>
      )}
    </div>
  );
};

export default DataSourceTag;
