import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchRings, ApiError } from '../api';
import type { RingPage, ReviewStatus, RingFilterParams } from '../types';
import {
  formatScore,
  formatDate,
  getReasonSentence,
  getRiskLevel,
} from '../constants';
import './RingListScreen.css';

interface FilterState {
  minScorePct: string; // percentage string (0–100)
  status: string;
  promotion: string;
  dateFrom: string;
  dateTo: string;
}

const EMPTY_FILTERS: FilterState = {
  minScorePct: '',
  status: '',
  promotion: '',
  dateFrom: '',
  dateTo: '',
};

export default function RingListScreen() {
  const [searchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') ?? '';
  const initialMinScorePct = searchParams.get('min_score') ?? '';

  const [filters, setFilters] = useState<FilterState>({
    ...EMPTY_FILTERS,
    minScorePct: initialMinScorePct,
    status: initialStatus,
  });
  const [appliedFilters, setAppliedFilters] = useState<FilterState>({
    ...EMPTY_FILTERS,
    minScorePct: initialMinScorePct,
    status: initialStatus,
  });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<RingPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (currentPage: number, currentFilters: FilterState) => {
      setLoading(true);
      setError(null);

      const params: RingFilterParams = {
        page: currentPage,
        page_size: 20,
      };
      if (currentFilters.minScorePct !== '') {
        const pct = parseFloat(currentFilters.minScorePct);
        if (!isNaN(pct) && pct > 0) {
          params.min_score = pct / 100;
        }
      }
      if (currentFilters.status) {
        params.status = currentFilters.status as ReviewStatus;
      }
      if (currentFilters.promotion.trim()) {
        params.promotion = currentFilters.promotion.trim();
      }
      if (currentFilters.dateFrom) {
        params.date_from = currentFilters.dateFrom;
      }
      if (currentFilters.dateTo) {
        params.date_to = currentFilters.dateTo;
      }

      fetchRings(params)
        .then(setData)
        .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
        .finally(() => setLoading(false));
    },
    [],
  );

  // Initial load (and when page changes)
  useEffect(() => {
    load(page, appliedFilters);
  }, [page, appliedFilters, load]);

  function handleApplyFilters(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setAppliedFilters({ ...filters });
  }

  function handleClearFilters() {
    setFilters({ ...EMPTY_FILTERS });
    setPage(1);
    setAppliedFilters({ ...EMPTY_FILTERS });
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="ring-list">
      <div className="ring-list-heading">
        <span className="ring-list-kicker">Detection run</span>
        <h1 className="page-title">Abuse rings</h1>
        <p>Investigate and review coordinated multi-account promotional abuse rings.</p>
      </div>

      {/* Filter bar */}
      <form className="panel filter-bar" onSubmit={handleApplyFilters}>
        <div className="panel-header">Filter rings</div>
        <div className="filter-fields">
          <div className="filter-field">
            <label htmlFor="filter-min-score">Min Score (%)</label>
            <input
              id="filter-min-score"
              type="number"
              min="0"
              max="100"
              step="1"
              placeholder="0"
              value={filters.minScorePct}
              onChange={(e) =>
                setFilters((f) => ({ ...f, minScorePct: e.target.value }))
              }
            />
          </div>
          <div className="filter-field">
            <label htmlFor="filter-status">Review Status</label>
            <select
              id="filter-status"
              value={filters.status}
              onChange={(e) =>
                setFilters((f) => ({ ...f, status: e.target.value }))
              }
            >
              <option value="">All statuses</option>
              <option value="new">New</option>
              <option value="reviewing">Reviewing</option>
              <option value="confirmed">Confirmed</option>
              <option value="dismissed">Dismissed</option>
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="filter-promotion">Promotion ID</label>
            <input
              id="filter-promotion"
              type="text"
              placeholder="e.g. PROMO_10"
              value={filters.promotion}
              onChange={(e) =>
                setFilters((f) => ({ ...f, promotion: e.target.value }))
              }
            />
          </div>
          <div className="filter-field">
            <label htmlFor="filter-date-from">Created After</label>
            <input
              id="filter-date-from"
              type="date"
              value={filters.dateFrom}
              onChange={(e) =>
                setFilters((f) => ({ ...f, dateFrom: e.target.value }))
              }
            />
          </div>
          <div className="filter-field">
            <label htmlFor="filter-date-to">Created Before</label>
            <input
              id="filter-date-to"
              type="date"
              value={filters.dateTo}
              onChange={(e) =>
                setFilters((f) => ({ ...f, dateTo: e.target.value }))
              }
            />
          </div>
        </div>
        <div className="filter-actions">
          <button type="submit" className="btn-primary">
            Apply Filters
          </button>
          <button type="button" onClick={handleClearFilters}>
            Clear
          </button>
        </div>
      </form>

      {/* Results */}
      {loading && (
        <div className="panel ring-table-wrap skeleton-pulse">
          <table className="ring-table">
            <thead>
              <tr>
                <th>Risk Level</th>
                <th>Status</th>
                <th>Ring ID</th>
                <th>Members</th>
                <th>Shared</th>
                <th>Entity Types</th>
                <th>Why this was flagged</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <tr key={i}>
                  <td>
                    <span className="skeleton-box" style={{ width: 80, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 50, height: 16 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 110, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 24, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 24, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 90, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 130, height: 14 }} />
                  </td>
                  <td>
                    <span className="skeleton-box" style={{ width: 70, height: 14 }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error && (
        <div className="inline-error">
          <p>{error}</p>
          <button onClick={() => load(page, appliedFilters)} style={{ marginTop: 8 }}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && data && data.items.length === 0 && (
        <div className="panel" style={{ textAlign: 'center', padding: 32 }}>
          <p className="text-muted">No rings match the current filters.</p>
          <button onClick={handleClearFilters} style={{ marginTop: 12 }}>
            Clear filters
          </button>
        </div>
      )}

      {!loading && !error && data && data.items.length > 0 && (
        <>
          <div className="panel ring-table-wrap">
            <table className="ring-table">
              <thead>
                <tr>
                  <th>Risk Level</th>
                  <th>Status</th>
                  <th>Ring ID</th>
                  <th>Members</th>
                  <th>Shared</th>
                  <th>Entity Types</th>
                  <th>Why this was flagged</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((ring) => {
                  const scoreColor =
                    ring.score >= 0.8
                      ? 'var(--score-high)'
                      : ring.score >= 0.5
                        ? 'var(--score-medium)'
                        : 'var(--score-low)';

                  const reasonSentences = ring.reason_codes.map(getReasonSentence);
                  const maxReasons = 3;
                  const shown = reasonSentences.slice(0, maxReasons);
                  const overflow = reasonSentences.length - maxReasons;

                  return (
                    <tr key={ring.ring_id}>
                      <td>
                        <div className="risk-score">
                          <span
                            className="risk-score-label"
                            style={{ color: scoreColor }}
                          >
                            {getRiskLevel(ring.score)}
                          </span>
                          <div className="score-bar">
                            <div className="score-bar-fill">
                              <div
                                className="score-bar-fill-inner"
                                style={{
                                  width: `${ring.score * 100}%`,
                                  background: scoreColor,
                                }}
                              />
                            </div>
                            <span className="risk-score-exact mono">
                              {formatScore(ring.score)}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`status-badge status-${ring.status}`}>
                          {ring.status}
                        </span>
                      </td>
                      <td>
                        <Link to={`/rings/${ring.ring_id}`} className="mono ring-id-link">
                          {ring.ring_id} <span className="ring-id-arrow" aria-hidden="true">→</span>
                        </Link>
                      </td>
                      <td className="mono">{ring.member_count}</td>
                      <td className="mono">{ring.shared_entity_count}</td>
                      <td>{ring.entity_types.join(', ')}</td>
                      <td>
                        <div className="reason-pills">
                          {shown.map((label, i) => (
                            <span key={i} className="reason-pill">
                              {label}
                            </span>
                          ))}
                          {overflow > 0 && (
                            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                              +{overflow} more
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="text-secondary">{formatDate(ring.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <span className="pagination-info mono">
              Page {data.page} of {totalPages} ({data.total.toLocaleString()} rings)
            </span>
            <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
