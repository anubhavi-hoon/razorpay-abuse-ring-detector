import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchSummary, ApiError } from '../api';
import type { SummaryResponse, ReviewStatus } from '../types';
import './DashboardScreen.css';

export default function DashboardScreen() {
  const [data, setData] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSummary()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="dashboard skeleton-pulse">
        <h1 className="page-title">
          <span className="skeleton-box" style={{ width: 140, height: 24 }} />
        </h1>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 100, height: 14 }} />
          </div>
          <div className="metrics-row">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="metric">
                <span
                  className="skeleton-box"
                  style={{ width: 60, height: 28, marginBottom: 4 }}
                />
                <span className="skeleton-box" style={{ width: 80, height: 14 }} />
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 120, height: 14 }} />
          </div>
          <div className="score-dist">
            {[1, 2, 3].map((i) => (
              <div key={i} className="score-dist-row">
                <span className="skeleton-box" style={{ width: 50, height: 14 }} />
                <div className="score-dist-bar-track" />
                <span className="skeleton-box" style={{ width: 30, height: 14 }} />
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 100, height: 14 }} />
          </div>
          <div className="review-status-row">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="review-status-item"
                style={{ pointerEvents: 'none' }}
              >
                <span
                  className="skeleton-box"
                  style={{ width: 36, height: 22, marginBottom: 4 }}
                />
                <span className="skeleton-box" style={{ width: 55, height: 12 }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="inline-error">
        <p>{error}</p>
        <button onClick={() => window.location.reload()} style={{ marginTop: 8 }}>
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const scoreDist = data.score_distribution;
  const scoreTotal =
    (scoreDist.low ?? 0) + (scoreDist.medium ?? 0) + (scoreDist.high ?? 0);

  const statusEntries: { key: ReviewStatus; label: string }[] = [
    { key: 'new', label: 'New' },
    { key: 'reviewing', label: 'Reviewing' },
    { key: 'confirmed', label: 'Confirmed' },
    { key: 'dismissed', label: 'Dismissed' },
  ];

  return (
    <div className="dashboard">
      <h1 className="page-title">Dashboard</h1>

      {/* Summary metrics */}
      <div className="panel dashboard-metrics">
        <div className="panel-header">Run Summary</div>
        <div className="metrics-row">
          <div className="metric">
            <span className="metric-value">{data.account_count.toLocaleString()}</span>
            <span className="metric-label">Accounts</span>
          </div>
          <div className="metric">
            <span className="metric-value">
              {data.transaction_count.toLocaleString()}
            </span>
            <span className="metric-label">Transactions</span>
          </div>
          <div className="metric">
            <span className="metric-value">
              {data.scored_account_count.toLocaleString()}
            </span>
            <span className="metric-label">Scored</span>
          </div>
          <div className="metric">
            <span className="metric-value">
              {data.flagged_account_count.toLocaleString()}
            </span>
            <span className="metric-label">Flagged</span>
          </div>
          <div className="metric">
            <span className="metric-value">{data.ring_count.toLocaleString()}</span>
            <span className="metric-label">Rings</span>
          </div>
        </div>
      </div>

      {/* Score distribution */}
      <div className="panel dashboard-scores">
        <div className="panel-header">Score Distribution</div>
        {scoreTotal > 0 ? (
          <div className="score-dist">
            {(['low', 'medium', 'high'] as const).map((bucket) => {
              const count = scoreDist[bucket] ?? 0;
              const pct = scoreTotal > 0 ? (count / scoreTotal) * 100 : 0;
              return (
                <div key={bucket} className="score-dist-row">
                  <span className="score-dist-label">
                    {bucket.charAt(0).toUpperCase() + bucket.slice(1)}
                  </span>
                  <div className="score-dist-bar-track">
                    <div
                      className={`score-dist-bar-fill score-dist-bar--${bucket}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="score-dist-count mono">{count}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-muted">No scored rings.</p>
        )}
      </div>

      {/* Review status */}
      <div className="panel dashboard-review">
        <div className="panel-header">Review Status</div>
        <div className="review-status-row">
          {statusEntries.map(({ key, label }) => (
            <Link
              key={key}
              to={`/rings?status=${key}`}
              className={`review-status-item status-${key}`}
            >
              <span className="review-status-count mono">
                {(data.review_status_totals[key] ?? 0).toLocaleString()}
              </span>
              <span className="review-status-label">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
