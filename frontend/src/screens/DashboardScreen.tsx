import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  analyzeUpload,
  fetchRings,
  fetchSummary,
  reportUrl,
  ApiError,
} from '../api';
import type { SummaryResponse, ReviewStatus } from '../types';
import { SCORE_BUCKETS } from '../constants';
import { useToast } from '../components/toastContext';
import './DashboardScreen.css';

const ACCOUNTS_TEMPLATE =
  'account_id,created_at,email_hash,phone_hash,device_id,ip_address,payment_instrument_id\n';
const TRANSACTIONS_TEMPLATE =
  'transaction_id,account_id,merchant_id,promotion_id,amount,created_at,status\n';

function templateHref(csv: string) {
  return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
}

export default function DashboardScreen() {
  const [data, setData] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [highRiskNewCount, setHighRiskNewCount] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [accountsFile, setAccountsFile] = useState<File | null>(null);
  const [transactionsFile, setTransactionsFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [showColdStartNotice, setShowColdStartNotice] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (!loading) {
      setShowColdStartNotice(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowColdStartNotice(true);
    }, 1500);
    return () => clearTimeout(timer);
  }, [loading]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchSummary(),
      fetchRings({
        page: 1,
        page_size: 1,
        min_score: SCORE_BUCKETS.high.min,
        status: 'new',
      }),
    ])
      .then(([summary, highRiskNew]) => {
        if (!cancelled) {
          setData(summary);
          setHighRiskNewCount(highRiskNew.total);
        }
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
  }, [reloadKey]);

  async function handleAnalyze() {
    if (!accountsFile || !transactionsFile) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeUpload(accountsFile, transactionsFile);
      addToast(
        `Analyzed ${result.account_count.toLocaleString()} accounts, found ${result.ring_count.toLocaleString()} rings`,
        'success',
      );
      setReloadKey((key) => key + 1);
    } catch (e) {
      setAnalyzeError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }

  const uploadPanel = (
    <div className="panel analyze-panel">
      <div className="panel-header">Analyze Test Data</div>
      <p className="analyze-warning" role="note">
        Use synthetic or pre-hashed test data only. Do not upload real personal
        information.
      </p>
      <div className="analyze-fields">
        <div className="analyze-field">
          <label htmlFor="analyze-accounts">Accounts CSV</label>
          <input
            id="analyze-accounts"
            type="file"
            accept=".csv,text/csv"
            disabled={analyzing}
            onChange={(e) => setAccountsFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="analyze-field">
          <label htmlFor="analyze-transactions">Transactions CSV</label>
          <input
            id="analyze-transactions"
            type="file"
            accept=".csv,text/csv"
            disabled={analyzing}
            onChange={(e) => setTransactionsFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>
      <div className="analyze-actions">
        <button
          className="btn btn-primary"
          disabled={analyzing || !accountsFile || !transactionsFile}
          onClick={handleAnalyze}
        >
          {analyzing ? 'Analyzing…' : 'Analyze'}
        </button>
        <span className="text-muted analyze-templates">
          Templates:{' '}
          <a href={templateHref(ACCOUNTS_TEMPLATE)} download="accounts.csv">
            accounts.csv
          </a>{' '}
          <a href={templateHref(TRANSACTIONS_TEMPLATE)} download="transactions.csv">
            transactions.csv
          </a>
        </span>
      </div>
      <p className="text-muted analyze-hint">
        Max 5 MB per file, 5,000 accounts, 25,000 transactions. Optional{' '}
        <code className="mono">label</code> and{' '}
        <code className="mono">ring_label</code> columns may be appended to
        accounts.csv; without them no evaluation metrics are reported.
      </p>
      {analyzing && <p className="loading-text">Scoring accounts and detecting rings…</p>}
      {analyzeError && (
        <p className="analyze-error" role="alert">
          {analyzeError}
        </p>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="dashboard skeleton-pulse">
        {showColdStartNotice && (
          <div className="dashboard-coldstart-notice" role="status" aria-live="polite">
            <span className="dashboard-coldstart-dot" aria-hidden="true" />
            <span>Waking the analysis service — free hosting may take up to a minute.</span>
          </div>
        )}
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
      <div className="dashboard">
        <div className="inline-error">
          <p>{error}</p>
          <button onClick={() => setReloadKey((key) => key + 1)} style={{ marginTop: 8 }}>
            Retry
          </button>
        </div>
        {uploadPanel}
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
      <div className="dashboard-heading">
        <div>
          <span className="dashboard-kicker">Live detection run</span>
          <h1 className="page-title">Investigation overview</h1>
          <p>Prioritize coordinated abuse rings, then follow the shared signals.</p>
        </div>
        <Link to="/rings" className="dashboard-browse-link">
          Browse all rings <span aria-hidden="true">→</span>
        </Link>
      </div>

      <Link
        to={`/rings?min_score=${SCORE_BUCKETS.high.min * 100}&status=new`}
        className="high-risk-callout"
      >
        <span className="high-risk-callout-message">
          <strong className="mono">{highRiskNewCount.toLocaleString()}</strong>{' '}
          high-risk cases need attention
        </span>
        <span className="high-risk-callout-action">
          Review high-risk new cases <span aria-hidden="true">→</span>
        </span>
      </Link>

      <div className="dashboard-overview-grid">
        {/* Summary metrics */}
        <div className="panel dashboard-metrics">
          <div className="dashboard-panel-heading">
            <div className="panel-header">Run summary</div>
            <div className="dashboard-export-actions" aria-label="Export current report">
              <a className="btn" href={reportUrl('csv')}>Export CSV</a>
              <a className="btn" href={reportUrl('json')}>Export JSON</a>
            </div>
          </div>
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
          <div className="panel-header">Risk distribution</div>
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
          <div className="panel-header">Investigation queue</div>
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
                <span className="review-status-arrow" aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {uploadPanel}
    </div>
  );
}
