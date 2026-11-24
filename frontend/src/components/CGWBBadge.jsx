import React from 'react';

/**
 * CGWBBadge — displays the CGWB groundwater category with color coding.
 *
 * SAFE          → green   (stage ≤ 70%)
 * SEMI-CRITICAL → yellow  (70% < stage ≤ 90%)
 * CRITICAL      → orange  (90% < stage ≤ 100%)
 * OVER-EXPLOITED → red    (stage > 100%)
 *
 * Props:
 *   category: string  — "SAFE" | "SEMI-CRITICAL" | "CRITICAL" | "OVER-EXPLOITED"
 *   stage:    number  — the numeric extraction stage (optional, for tooltip)
 *   size:     string  — "sm" | "md" (default "md")
 */
const CGWBBadge = ({ category, stage, size = 'md' }) => {
  if (!category) return null;

  const categoryConfig = {
    'SAFE':           { emoji: '🟢', cssClass: 'cgwb-safe',           label: 'SAFE' },
    'SEMI-CRITICAL':  { emoji: '🟡', cssClass: 'cgwb-semi-critical',  label: 'SEMI-CRITICAL' },
    'CRITICAL':       { emoji: '🟠', cssClass: 'cgwb-critical',       label: 'CRITICAL' },
    'OVER-EXPLOITED': { emoji: '🔴', cssClass: 'cgwb-over-exploited', label: 'OVER-EXPLOITED' },
  };

  const config = categoryConfig[category.toUpperCase()] || {
    emoji: '⚪', cssClass: 'cgwb-unknown', label: category,
  };

  const tooltip = stage !== undefined && stage !== null
    ? `Stage: ${stage.toFixed ? stage.toFixed(2) : stage}% — ${config.label}`
    : config.label;

  return (
    <span
      className={`cgwb-badge ${config.cssClass} cgwb-${size}`}
      title={tooltip}
    >
      {config.emoji} {config.label}
    </span>
  );
};

export default CGWBBadge;
