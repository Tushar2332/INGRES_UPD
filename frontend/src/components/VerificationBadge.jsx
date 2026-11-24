import React from 'react';

/**
 * VerificationBadge — displays ✓ Verified or ⚠ Unverified based on backend response.
 * Props:
 *   verified: bool | null
 *   issues:   string[]
 */
const VerificationBadge = ({ verified, issues = [] }) => {
  if (verified === null || verified === undefined) return null;

  if (verified) {
    return (
      <span className="verification-badge verified" title="All numbers verified against INGRES database">
        ✓ Verified
      </span>
    );
  }

  const tooltip = issues.length > 0
    ? `Issues: ${issues.join('; ')}`
    : 'Some values could not be verified against the database';

  return (
    <span className="verification-badge unverified" title={tooltip}>
      ⚠ Unverified
    </span>
  );
};

export default VerificationBadge;
