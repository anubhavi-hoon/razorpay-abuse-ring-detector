import { useState, useMemo, useId } from 'react';
import {
  FEATURE_CATEGORIES,
  getFeatureMeta,
  formatFeatureValue,
} from '../constants';
import type { FeatureCategory } from '../constants';
import './FeatureExplorer.css';

interface FeatureExplorerProps {
  features: Record<string, number>;
}

export function FeatureExplorerSkeleton() {
  return (
    <div className="panel feature-explorer skeleton-pulse">
      <div className="feature-explorer-header">
        <div>
          <span className="skeleton-box" style={{ width: 140, height: 16, marginBottom: 6 }} />
          <span className="skeleton-box" style={{ width: 280, height: 13 }} />
        </div>
        <span className="skeleton-box" style={{ width: 100, height: 22 }} />
      </div>
      <div className="feature-categories-bar">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <span key={i} className="skeleton-box" style={{ width: 70, height: 28, borderRadius: 14 }} />
        ))}
      </div>
      <div className="feature-grid">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="feature-card">
            <span className="skeleton-box" style={{ width: 120, height: 14, marginBottom: 8 }} />
            <span className="skeleton-box" style={{ width: 80, height: 20, marginBottom: 8 }} />
            <span className="skeleton-box" style={{ width: 100, height: 12 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FeatureExplorer({ features }: FeatureExplorerProps) {
  const [selectedCategory, setSelectedCategory] = useState<'all' | FeatureCategory>('all');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const baseId = useId();

  const featureEntries = useMemo(() => {
    return Object.entries(features).map(([key, value]) => {
      const meta = getFeatureMeta(key);
      return { key, value, meta };
    });
  }, [features]);

  const filteredEntries = useMemo(() => {
    if (selectedCategory === 'all') {
      return featureEntries;
    }
    return featureEntries.filter((item) => item.meta.category === selectedCategory);
  }, [featureEntries, selectedCategory]);

  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const totalCount = featureEntries.length;
  const countLabel =
    selectedCategory === 'all'
      ? `${totalCount} observed signals`
      : `${filteredEntries.length} of ${totalCount} signals`;

  return (
    <div className="panel feature-explorer">
      {/* Header */}
      <div className="feature-explorer-header">
        <div>
          <h2 className="panel-header" style={{ marginBottom: 4 }}>Behavioral evidence</h2>
          <p className="feature-explorer-desc">
            Signals observed for this account at the analysis cutoff. These values support
            investigation but do not independently prove abuse.
          </p>
        </div>
        <span className="feature-count-pill mono">{countLabel}</span>
      </div>

      {/* Category controls */}
      <div className="feature-categories-bar" role="tablist" aria-label="Feature categories">
        {FEATURE_CATEGORIES.map((cat) => {
          const isActive = selectedCategory === cat.key;
          return (
            <button
              key={cat.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-pressed={isActive}
              className={`feature-cat-btn ${isActive ? 'feature-cat-btn--active' : ''}`}
              onClick={() => setSelectedCategory(cat.key)}
            >
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* Feature grid */}
      <div className="feature-grid" role="region" aria-label="Behavioral features list">
        {filteredEntries.map(({ key, value, meta }) => {
          const isExpanded = expandedKeys.has(key);
          const formattedValue = formatFeatureValue(key, value);
          const descId = `${baseId}-desc-${key}`;
          const isRatio = meta.isRatio && typeof value === 'number';
          const ratioPercent = isRatio ? Math.min(100, Math.max(0, value * 100)) : 0;

          return (
            <div
              key={key}
              className={`feature-card ${meta.isSharedIdentity ? 'feature-card--shared' : ''}`}
            >
              <div className="feature-card-header">
                <span className="feature-card-label">{meta.label}</span>
                <span className="feature-card-category-badge">
                  {meta.isSharedIdentity && (
                    <span className="feature-shared-icon" aria-hidden="true" title="Shared identity signal">
                      ⬡
                    </span>
                  )}
                  {meta.category.replace('_', ' ')}
                </span>
              </div>

              <div className="feature-card-value-row">
                <span className="feature-card-value mono">{formattedValue}</span>
                {isRatio && (
                  <div className="feature-ratio-bar-wrap" title={`${ratioPercent.toFixed(1)}%`}>
                    <div className="feature-ratio-bar-track">
                      <div
                        className="feature-ratio-bar-fill"
                        style={{ width: `${ratioPercent}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Disclosure Toggle */}
              <button
                type="button"
                className="feature-disclosure-btn"
                onClick={() => toggleExpand(key)}
                aria-expanded={isExpanded}
                aria-controls={descId}
              >
                <span>What this measures</span>
                <span
                  className={`feature-disclosure-chevron ${
                    isExpanded ? 'feature-disclosure-chevron--open' : ''
                  }`}
                  aria-hidden="true"
                >
                  ▾
                </span>
              </button>

              {/* Collapsible Details */}
              {isExpanded && (
                <div id={descId} className="feature-card-description">
                  <p>{meta.description}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
