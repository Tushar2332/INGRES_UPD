import React from 'react';
import DataCard from './DataCard';
import ChartDisplay from './ChartDisplay';
import VerificationBadge from './VerificationBadge';
import CGWBBadge from './CGWBBadge';
import DataSourceTag from './DataSourceTag';

/**
 * MessageBubble — renders a single chat message with all Review 2 enrichments:
 *   - VerificationBadge (✓ Verified / ⚠ Unverified)
 *   - CGWBBadge for messages with a category result
 *   - DataSourceTag (source, year, confidence)
 *   - ChartDisplay
 *   - DataCards
 *   - Suggestion chips
 */
const MessageBubble = ({ message, onSuggestionClick }) => {
  const isBot = message.type === 'bot';

  // Format markdown-style bold (**text**) in bot messages
  const formatText = (text) => {
    if (!text) return '';
    return text
      .split('\n')
      .map((line, i) => {
        const parts = line.split(/\*\*(.*?)\*\*/g);
        return (
          <span key={i}>
            {parts.map((part, j) =>
              j % 2 === 1 ? <strong key={j}>{part}</strong> : part
            )}
            {i < text.split('\n').length - 1 && <br />}
          </span>
        );
      });
  };

  return (
    <div className={`message-bubble ${message.type}`}>
      <div className="message-content">
        {/* Main text */}
        <p className="message-text">{isBot ? formatText(message.text) : message.text}</p>

        {/* Bot-only enrichments */}
        {isBot && (
          <>
            {/* Verification + CGWB badges row */}
            {(message.verified !== undefined || message.cgwbCategory) && (
              <div className="message-badges">
                <VerificationBadge
                  verified={message.verified}
                  issues={message.verificationIssues || []}
                />
                {message.cgwbCategory && (
                  <CGWBBadge category={message.cgwbCategory} size="sm" />
                )}
              </div>
            )}

            {/* Chart */}
            {message.chartData && (
              <ChartDisplay chartData={message.chartData} />
            )}

            {/* Data cards */}
            {message.data && message.data.length > 0 && (
              <div className="data-cards">
                {message.data.map((item, idx) => (
                  <DataCard key={idx} data={item} />
                ))}
              </div>
            )}

            {/* Suggestions */}
            {message.suggestions && message.suggestions.length > 0 && (
              <div className="suggestions">
                <span className="suggestions-label">💡 Try these:</span>
                {message.suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    className="suggestion-chip"
                    onClick={() => onSuggestionClick(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Data source tag */}
            {(message.assessmentYear || message.dataSource) && (
              <DataSourceTag
                assessmentYear={message.assessmentYear}
                dataSource={message.dataSource}
                dataConfidence={message.dataConfidence}
              />
            )}
          </>
        )}
      </div>

      <span className="message-time">{message.timestamp}</span>
    </div>
  );
};

export default MessageBubble;
