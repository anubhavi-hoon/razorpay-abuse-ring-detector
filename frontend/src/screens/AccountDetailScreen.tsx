import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchAccountDetail, ApiError } from '../api';
import type { AccountDetail } from '../types';
import { formatScore, formatDateTime, getReasonSentence } from '../constants';
import './AccountDetailScreen.css';

export default function AccountDetailScreen() {
  const { accountId } = useParams<{ accountId: string }>();
  const [data, setData] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAccountDetail(accountId)
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
  }, [accountId]);

  if (loading) {
    return (
      <div className="account-detail skeleton-pulse">
        <div className="panel">
          <span
            className="skeleton-box"
            style={{ width: 180, height: 26, marginBottom: 8 }}
          />
          <div className="account-header-meta">
            <span className="skeleton-box" style={{ width: 80, height: 16 }} />
            <span className="skeleton-box" style={{ width: 60, height: 16 }} />
            <span className="skeleton-box" style={{ width: 140, height: 16 }} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 80, height: 14 }} />
          </div>
          <div className="identity-grid">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="identity-field">
                <span
                  className="skeleton-box"
                  style={{ width: 80, height: 12, marginBottom: 4 }}
                />
                <span
                  className="skeleton-box"
                  style={{ width: 140, height: 16 }}
                />
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
                style={{ width: 130, height: 22 }}
              />
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="skeleton-box" style={{ width: 70, height: 14 }} />
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {[1, 2, 3].map((i) => (
                  <tr key={i}>
                    <td>
                      <span
                        className="skeleton-box"
                        style={{ width: 140, height: 14 }}
                      />
                    </td>
                    <td>
                      <span
                        className="skeleton-box"
                        style={{ width: 60, height: 14 }}
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

  const scoreColor =
    data.ml_score >= 0.8
      ? 'var(--score-high)'
      : data.ml_score >= 0.5
        ? 'var(--score-medium)'
        : 'var(--score-low)';

  const identityFields: { label: string; value: string }[] = [
    { label: 'Email Hash', value: data.email_hash },
    { label: 'Phone Hash', value: data.phone_hash },
    { label: 'Device ID', value: data.device_id },
    { label: 'IP Address', value: data.ip_address },
    { label: 'Payment Instrument', value: data.payment_instrument_id },
  ];

  function formatFeatureValue(key: string, value: number): string {
    if (key.toLowerCase().includes('ratio')) {
      return `${(value * 100).toFixed(2)}%`;
    }
    return value.toFixed(2);
  }

  return (
    <div className="account-detail">
      {/* Header */}
      <div className="panel">
        <h1 className="page-title mono">{data.account_id}</h1>
        <div className="account-header-meta">
          <div className="score-bar">
            <div className="score-bar-fill">
              <div
                className="score-bar-fill-inner"
                style={{
                  width: `${data.ml_score * 100}%`,
                  background: scoreColor,
                }}
              />
            </div>
            <span className="mono">{formatScore(data.ml_score)}</span>
          </div>
          <span
            className={`status-badge ${
              data.predicted_label === 1 ? 'status-confirmed' : 'status-dismissed'
            }`}
          >
            {data.predicted_label === 1 ? 'Flagged' : 'Normal'}
          </span>
          <span className="text-secondary">
            Created {formatDateTime(data.created_at)}
          </span>
        </div>
      </div>

      {/* Identity */}
      <div className="panel">
        <div className="panel-header">Identity</div>
        <div className="identity-grid">
          {identityFields.map((f) => (
            <div key={f.label} className="identity-field">
              <span className="identity-label">{f.label}</span>
              <span className="identity-value mono">{f.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Reason codes */}
      <div className="panel">
        <div className="panel-header">Reason Codes</div>
        <div className="reason-pills">
          {data.reason_codes.map((code) => (
            <span key={code} className="reason-pill">
              {getReasonSentence(code)}
            </span>
          ))}
        </div>
      </div>

      {/* Features */}
      <div className="panel">
        <div className="panel-header">Features</div>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Feature</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.features).map(([key, value]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td className="mono">{formatFeatureValue(key, value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ring membership */}
      <div className="panel">
        <div className="panel-header">Ring Membership</div>
        {data.ring_ids.length > 0 ? (
          <div className="ring-links">
            {data.ring_ids.map((rid) => (
              <Link key={rid} to={`/rings/${rid}`} className="mono">
                {rid}
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-muted">No ring memberships.</p>
        )}
      </div>

      {/* Transactions */}
      <div className="panel">
        <div className="panel-header">Transactions</div>
        {data.transactions.length > 0 ? (
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Transaction ID</th>
                  <th>Merchant</th>
                  <th>Promotion</th>
                  <th>Amount</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.transactions.map((txn) => (
                  <tr key={txn.transaction_id}>
                    <td className="mono">{txn.transaction_id}</td>
                    <td>{txn.merchant_id}</td>
                    <td className="mono">{txn.promotion_id ?? '—'}</td>
                    <td className="mono">{txn.amount.toFixed(2)}</td>
                    <td className="text-secondary">
                      {formatDateTime(txn.created_at)}
                    </td>
                    <td>
                      <span
                        className={`txn-status txn-status--${txn.status}`}
                      >
                        {txn.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted">No transactions.</p>
        )}
      </div>
    </div>
  );
}
