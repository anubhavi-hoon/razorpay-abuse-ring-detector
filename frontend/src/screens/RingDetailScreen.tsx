import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchRingDetail, updateRingStatus, ApiError } from '../api';
import type { RingDetail, ReviewStatus } from '../types';
import {
  formatScore,
  formatDate,
  getReasonSentence,
  getRiskLevel,
  REVIEW_TRANSITIONS,
  getTransitionLabel,
} from '../constants';
import { useToast } from '../components/toastContext';
import RelationshipGraph from '../components/RelationshipGraph';
import './RingDetailScreen.css';

export default function RingDetailScreen() {
  const { ringId } = useParams<{ ringId: string }>();
  const { addToast } = useToast();

  const [data, setData] = useState<RingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!ringId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRingDetail(ringId)
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
  }, [ringId]);

  async function handleStatusChange(newStatus: ReviewStatus) {
    if (!ringId || !data || updating) return;
    setUpdating(true);
    try {
      const res = await updateRingStatus(ringId, newStatus);
      setData((prev) => (prev ? { ...prev, status: res.status } : prev));
      addToast(`Status updated to "${res.status}"`, 'success');
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      addToast(msg, 'error');
    } finally {
      setUpdating(false);
    }
  }

  if (loading) {
    return (
      <div className="ring-detail skeleton-pulse">
        <div className="panel ring-detail-header">
          <div className="ring-detail-header-top">
            <div>
              <span
                className="skeleton-box"
                style={{ width: 220, height: 26, marginBottom: 8 }}
              />
              <div className="ring-detail-meta">
                <span className="skeleton-box" style={{ width: 80, height: 16 }} />
                <span className="skeleton-box" style={{ width: 60, height: 16 }} />
                <span className="skeleton-box" style={{ width: 90, height: 16 }} />
              </div>
            </div>
            <div className="ring-detail-actions">
              <span className="skeleton-box" style={{ width: 110, height: 32 }} />
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 90, height: 14 }} />
          </div>
          <div className="metrics-grid">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <div key={i} className="metric-cell">
                <span
                  className="skeleton-box"
                  style={{ width: 90, height: 12, marginBottom: 4 }}
                />
                <span className="skeleton-box" style={{ width: 60, height: 18 }} />
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 100, height: 14 }} />
          </div>
          <div className="reason-pills">
            {[1, 2, 3].map((i) => (
              <span
                key={i}
                className="skeleton-box"
                style={{ width: 140, height: 22 }}
              />
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 130, height: 14 }} />
          </div>
          <div
            className="skeleton-box"
            style={{ width: '100%', height: 160 }}
          />
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 70, height: 14 }} />
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Account ID</th>
                  <th>ML Score</th>
                  <th>Why this was flagged</th>
                </tr>
              </thead>
              <tbody>
                {[1, 2, 3].map((i) => (
                  <tr key={i}>
                    <td>
                      <span
                        className="skeleton-box"
                        style={{ width: 100, height: 14 }}
                      />
                    </td>
                    <td>
                      <span
                        className="skeleton-box"
                        style={{ width: 60, height: 14 }}
                      />
                    </td>
                    <td>
                      <span
                        className="skeleton-box"
                        style={{ width: 180, height: 14 }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

  const allowedTransitions = REVIEW_TRANSITIONS[data.status] ?? [];
  const scoreColor =
    data.score >= 0.8
      ? 'var(--score-high)'
      : data.score >= 0.5
        ? 'var(--score-medium)'
        : 'var(--score-low)';

  return (
    <div className="ring-detail">
      {/* Header */}
      <div className="panel ring-detail-header">
        <div className="ring-detail-header-top">
          <div>
            <h1 className="page-title mono">{data.ring_id}</h1>
            <div className="ring-detail-meta">
              <div className="risk-score">
                <span
                  className="risk-score-label"
                  style={{ color: scoreColor }}
                >
                  {getRiskLevel(data.score)}
                </span>
                <div className="score-bar">
                  <div className="score-bar-fill">
                    <div
                      className="score-bar-fill-inner"
                      style={{
                        width: `${data.score * 100}%`,
                        background: scoreColor,
                      }}
                    />
                  </div>
                  <span className="risk-score-exact mono">
                    {formatScore(data.score)}
                  </span>
                </div>
              </div>
              <span className={`status-badge status-${data.status}`}>
                {data.status}
              </span>
              <span className="text-secondary">{formatDate(data.created_at)}</span>
            </div>
          </div>
          <div className="ring-detail-actions">
            {allowedTransitions.map((target) => (
              <button
                key={target}
                onClick={() => handleStatusChange(target)}
                disabled={updating}
                className={
                  target === 'confirmed' || target === 'dismissed'
                    ? ''
                    : 'btn-primary'
                }
              >
                {getTransitionLabel(data.status, target)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="panel">
        <div className="panel-header">Ring Metrics</div>
        <div className="metrics-grid">
          <div className="metric-cell">
            <span className="metric-cell-label">Density</span>
            <span className="metric-cell-value mono">
              {formatScore(data.density)}
            </span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Promotion Concentration</span>
            <span className="metric-cell-value mono">
              {formatScore(data.promotion_concentration)}
            </span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Mean ML Score</span>
            <span className="metric-cell-value mono">
              {formatScore(data.mean_ml_score)}
            </span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Max ML Score</span>
            <span className="metric-cell-value mono">
              {formatScore(data.max_ml_score)}
            </span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Temporal Concentration</span>
            <span className="metric-cell-value mono">
              {formatScore(data.temporal_concentration)}
            </span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Members</span>
            <span className="metric-cell-value mono">{data.member_count}</span>
          </div>
          <div className="metric-cell">
            <span className="metric-cell-label">Shared Entities</span>
            <span className="metric-cell-value mono">
              {data.shared_entity_count}
            </span>
          </div>
        </div>
      </div>

      {/* Reason codes */}
      <div className="panel">
        <div className="panel-header">Why this was flagged</div>
        <div className="reason-pills">
          {data.reason_codes.map((code) => (
            <span key={code} className="reason-pill">
              {getReasonSentence(code)}
            </span>
          ))}
        </div>
      </div>

      {/* Relationship graph */}
      <div className="panel">
        <div className="panel-header">Relationship Graph</div>
        <RelationshipGraph nodes={data.nodes} edges={data.edges} />
      </div>

      {/* Members table (accessible fallback) */}
      <div className="panel">
        <div className="panel-header">Members</div>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Account ID</th>
                <th>ML Score</th>
                <th>Why this was flagged</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map((m) => (
                <tr key={m.account_id}>
                  <td>
                    <Link to={`/accounts/${m.account_id}`} className="mono">
                      {m.account_id}
                    </Link>
                  </td>
                  <td className="mono">{formatScore(m.ml_score)}</td>
                  <td>
                    <div className="reason-pills">
                      {m.reason_codes.map((code) => (
                        <span key={code} className="reason-pill">
                          {getReasonSentence(code)}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shared entities */}
      <div className="panel">
        <div className="panel-header">Shared Entities</div>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Entity ID</th>
                <th>Type</th>
                <th>Label</th>
              </tr>
            </thead>
            <tbody>
              {data.shared_entities.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{e.id}</td>
                  <td>{e.type}</td>
                  <td>{e.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
