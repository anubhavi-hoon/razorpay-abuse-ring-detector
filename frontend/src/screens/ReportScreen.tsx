import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { fetchReportJson, reportUrl, ApiError } from '../api';
import type { ReportResponse, ReportRow, ReviewStatus } from '../types';
import './ReportScreen.css';

/* ------------------------------------------------------------------ */
/*  Helper formatting & data derivations                              */
/* ------------------------------------------------------------------ */

function formatTimestamp(isoStr: string | null | undefined): string {
  if (!isoStr) return 'Active Detection Run';
  try {
    const dt = new Date(isoStr);
    return dt.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short',
    });
  } catch {
    return isoStr;
  }
}

function formatEntityType(typeStr: string): string {
  return typeStr.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ------------------------------------------------------------------ */
/*  ReportScreen Component                                            */
/* ------------------------------------------------------------------ */

export default function ReportScreen() {
  const [data, setData] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Interactive filters
  const [riskFilter, setRiskFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | ReviewStatus>('all');
  const [displayLimit, setDisplayLimit] = useState<10 | 20 | 0>(10);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [activeHoverBar, setActiveHoverBar] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchReportJson()
      .then((report) => {
        if (!cancelled) {
          setData(report);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Compute deterministic findings and chart datasets
  const analysis = useMemo(() => {
    if (!data) return null;

    const { summary, rings } = data;
    const totalRings = summary.ring_count || rings.length;
    const highRiskRings = summary.score_distribution.high ?? 0;
    const mediumRiskRings = summary.score_distribution.medium ?? 0;
    const lowRiskRings = summary.score_distribution.low ?? 0;
    const highRiskShare = totalRings > 0 ? (highRiskRings / totalRings) * 100 : 0;
    const flaggedRate =
      summary.account_count > 0
        ? (summary.flagged_account_count / summary.account_count) * 100
        : 0;

    const newCases = summary.review_status_totals.new ?? 0;
    const reviewingCases = summary.review_status_totals.reviewing ?? 0;
    const confirmedCases = summary.review_status_totals.confirmed ?? 0;
    const dismissedCases = summary.review_status_totals.dismissed ?? 0;

    const highRiskNew = rings.filter(
      (r) => r.risk_level === 'high' && r.review_status === 'new',
    ).length;

    // Check if detection resilience was assessed for this run
    const resilienceAssessed = rings.some((r) => r.detection_resilience != null);

    // Resilience distribution
    const resilienceMap: Record<string, number> = { high: 0, moderate: 0, low: 0 };
    // Entity types distribution
    const sharedEntityCounts: Record<string, number> = {};
    // Critical entity types distribution
    const criticalEntityCounts: Record<string, number> = {};

    rings.forEach((r) => {
      if (r.detection_resilience) {
        resilienceMap[r.detection_resilience] = (resilienceMap[r.detection_resilience] || 0) + 1;
      }

      (r.entity_types || []).forEach((e) => {
        sharedEntityCounts[e] = (sharedEntityCounts[e] || 0) + 1;
      });

      (r.critical_entity_types || []).forEach((c) => {
        criticalEntityCounts[c] = (criticalEntityCounts[c] || 0) + 1;
      });
    });

    // Top critical entity type
    const topCriticalEntry = Object.entries(criticalEntityCounts).sort(
      (a, b) => b[1] - a[1],
    )[0];
    const topCriticalName = topCriticalEntry
      ? formatEntityType(topCriticalEntry[0])
      : null;
    const topCriticalCount = topCriticalEntry ? topCriticalEntry[1] : 0;

    // Dominant resilience
    const dominantResilience = Object.entries(resilienceMap).sort((a, b) => b[1] - a[1])[0];

    // Plain-language findings list
    const findings: { id: string; title: string; desc: string; tag: string }[] = [];

    findings.push({
      id: 'high-risk',
      title: 'High-Risk Severity',
      desc: `${highRiskRings} of ${totalRings} detected rings (${highRiskShare.toFixed(
        1,
      )}%) exhibit high risk (score ≥ 0.80), indicating coordinated multi-account infrastructure.`,
      tag: `${highRiskShare.toFixed(1)}% high risk`,
    });

    findings.push({
      id: 'review-queue',
      title: 'Analyst Triage Backlog',
      desc: `${newCases} rings currently await initial review, including ${highRiskNew} high-risk cases that require immediate operator inspection.`,
      tag: `${newCases} awaiting review`,
    });

    if (!resilienceAssessed) {
      findings.push({
        id: 'critical-bottleneck',
        title: 'Critical Evidence Types',
        desc: 'Detection Resilience was not assessed for this run.',
        tag: 'Unassessed',
      });
      findings.push({
        id: 'resilience',
        title: 'Detection Resilience Profile',
        desc: 'Detection Resilience was not assessed for this run.',
        tag: 'Unassessed',
      });
    } else {
      if (topCriticalName && topCriticalCount > 0) {
        findings.push({
          id: 'critical-bottleneck',
          title: 'Critical Shared Signals',
          desc: `${topCriticalName} is the most common critical shared signal, appearing in minimum evidence-loss cuts across ${topCriticalCount} rings.`,
          tag: 'Critical Signal',
        });
      } else {
        findings.push({
          id: 'critical-bottleneck',
          title: 'Critical Evidence Types',
          desc: 'No single signal type appears in every minimum evidence-loss cut across assessed rings.',
          tag: 'Evidence Loss Sets',
        });
      }

      if (dominantResilience && dominantResilience[1] > 0) {
        const resName = dominantResilience[0].toUpperCase();
        const resCount = dominantResilience[1];
        const resPct = totalRings > 0 ? (resCount / totalRings) * 100 : 0;
        const phrasing =
          resPct > 50
            ? `The majority of detected rings (${resCount} rings, ${resPct.toFixed(0)}%) exhibit ${resName} resilience against evidence loss.`
            : `The largest resilience group is ${resName} (${resCount} rings, ${resPct.toFixed(0)}% of detected rings).`;

        findings.push({
          id: 'resilience',
          title: 'Detection Resilience Profile',
          desc: phrasing,
          tag: `${resName} Resilience`,
        });
      } else {
        findings.push({
          id: 'resilience',
          title: 'Detection Resilience Profile',
          desc: 'Detection Resilience was not assessed for this run.',
          tag: 'Unassessed',
        });
      }
    }

    return {
      totalRings,
      highRiskRings,
      mediumRiskRings,
      lowRiskRings,
      highRiskShare,
      flaggedRate,
      newCases,
      reviewingCases,
      confirmedCases,
      dismissedCases,
      resilienceAssessed,
      resilienceMap,
      sharedEntityCounts,
      criticalEntityCounts,
      findings,
    };
  }, [data]);

  // Filtered rings for priority table
  const filteredRings = useMemo(() => {
    if (!data) return [];
    return data.rings.filter((r) => {
      if (riskFilter !== 'all' && r.risk_level !== riskFilter) return false;
      if (statusFilter !== 'all' && r.review_status !== statusFilter) return false;
      return true;
    });
  }, [data, riskFilter, statusFilter]);

  const displayedRings = useMemo(() => {
    if (displayLimit === 0) return filteredRings;
    return filteredRings.slice(0, displayLimit);
  }, [filteredRings, displayLimit]);

  if (loading) {
    return (
      <div className="report-screen">
        <div className="report-loading-container" aria-live="polite">
          <div className="report-loading-spinner" aria-hidden="true" />
          <h2>Generating Coordinated Promotional Abuse Analysis...</h2>
          <p className="text-secondary">Retrieving active run graph models and risk indicators</p>
        </div>
      </div>
    );
  }

  if (error || !data || !analysis) {
    return (
      <div className="report-screen">
        <div className="inline-error" role="alert">
          <h3>Failed to load analysis report</h3>
          <p>{error || 'An unexpected error occurred while fetching report data.'}</p>
          <button
            className="btn"
            onClick={() => window.location.reload()}
            style={{ marginTop: '12px' }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="report-screen">
      {/* ------------------------------------------------------------ */}
      {/*  Header & Metadata                                            */}
      {/* ------------------------------------------------------------ */}
      <header className="report-header panel">
        <div className="report-header-top">
          <div>
            <div className="report-product-badge">
              <span className="report-badge-dot" aria-hidden="true" />
              <span>Razorpay Fraud Workbench • Live Run</span>
            </div>
            <h1 className="report-title">Coordinated Promotional Abuse Analysis</h1>
            <p className="report-subtitle">
              Executive investigation report synthesizing behavioural anomaly scores,
              graph connectivity, and detection resilience.
            </p>
          </div>

          <div className="report-actions" aria-label="Report export options">
            <a
              href={reportUrl('pdf')}
              className="btn btn-primary btn-download-pdf"
              download
              id="report-download-pdf-btn"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
                aria-hidden="true"
              >
                <path
                  d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v1a1 1 0 001 1h8a1 1 0 001-1v-1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span>Download PDF</span>
            </a>

            <a
              href={reportUrl('csv')}
              className="btn"
              download
              id="report-export-csv-btn"
            >
              Export CSV
            </a>

            <a
              href={reportUrl('json')}
              className="btn"
              download
              id="report-export-json-btn"
            >
              Export JSON
            </a>

            <Link to="/dashboard" className="btn btn-back-dashboard">
              ← Dashboard
            </Link>
          </div>
        </div>

        <div className="report-meta-strip">
          <div className="report-meta-item">
            <span className="report-meta-label">Active Run ID</span>
            <span className="report-meta-value mono">{summary.run_id}</span>
          </div>
          <div className="report-meta-divider" aria-hidden="true" />
          <div className="report-meta-item">
            <span className="report-meta-label">Generated Timestamp</span>
            <span className="report-meta-value">{formatTimestamp(data.exported_at)}</span>
          </div>
          <div className="report-meta-divider" aria-hidden="true" />
          <div className="report-meta-item">
            <span className="report-meta-label">Total Accounts In Scope</span>
            <span className="report-meta-value mono">{summary.account_count.toLocaleString()}</span>
          </div>
          <div className="report-meta-divider" aria-hidden="true" />
          <div className="report-meta-item">
            <span className="report-meta-label">Total Rings Flagged</span>
            <span className="report-meta-value mono">{summary.ring_count.toLocaleString()}</span>
          </div>
        </div>

        {/* Decision-support disclaimer */}
        <div className="report-disclaimer-callout" role="note">
          <div className="report-disclaimer-icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="report-disclaimer-content">
            <strong>Decision-Support Notice:</strong> This analysis synthesizes behavioural
            heuristic flags and bipartite graph clustering to prioritize triage queues. Risk
            scores represent relative priority rankings for analyst inspection, not automated
            blocking rules. Human operator evaluation is required before taking account actions.
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------ */}
      {/*  Executive Summary KPIs                                       */}
      {/* ------------------------------------------------------------ */}
      <section className="report-section" aria-labelledby="kpi-heading">
        <h2 id="kpi-heading" className="section-title">Executive Summary</h2>
        <div className="kpi-grid">
          <div className="kpi-card">
            <span className="kpi-label">Accounts Analyzed</span>
            <span className="kpi-val mono">{summary.account_count.toLocaleString()}</span>
            <span className="kpi-sub">
              {summary.scored_account_count.toLocaleString()} accounts ML scored
            </span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Transactions Analyzed</span>
            <span className="kpi-val mono">{summary.transaction_count.toLocaleString()}</span>
            <span className="kpi-sub">Coordinated promotion volume</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Accounts Flagged</span>
            <span className="kpi-val mono">{summary.flagged_account_count.toLocaleString()}</span>
            <span className="kpi-sub kpi-rate">
              <strong>{analysis.flaggedRate.toFixed(1)}%</strong> of analyzed accounts
            </span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Rings Detected</span>
            <span className="kpi-val mono">{analysis.totalRings.toLocaleString()}</span>
            <span className="kpi-sub">Connected cluster networks</span>
          </div>

          <div className="kpi-card kpi-card--high-risk">
            <span className="kpi-label">High-Risk Rings</span>
            <span className="kpi-val mono">{analysis.highRiskRings.toLocaleString()}</span>
            <span className="kpi-sub">
              <strong>{analysis.highRiskShare.toFixed(1)}%</strong> ring share (score ≥ 0.80)
            </span>
          </div>

          <div className="kpi-card kpi-card--awaiting">
            <span className="kpi-label">Cases Awaiting Review</span>
            <span className="kpi-val mono">{analysis.newCases.toLocaleString()}</span>
            <span className="kpi-sub">
              {analysis.reviewingCases} cases currently in progress
            </span>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ */}
      {/*  Plain-Language Deterministic Findings                       */}
      {/* ------------------------------------------------------------ */}
      <section className="report-section" aria-labelledby="findings-heading">
        <div className="panel findings-panel">
          <div className="panel-header">Key Analytical Findings</div>
          <h2 id="findings-heading" className="visually-hidden">Key Analytical Findings</h2>
          <div className="findings-grid">
            {analysis.findings.map((f) => (
              <div key={f.id} className="finding-card">
                <div className="finding-card-header">
                  <span className="finding-tag">{f.tag}</span>
                </div>
                <h3 className="finding-title">{f.title}</h3>
                <p className="finding-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ */}
      {/*  Visual Summaries (Native SVG + CSS)                          */}
      {/* ------------------------------------------------------------ */}
      <section className="report-section" aria-labelledby="visuals-heading">
        <h2 id="visuals-heading" className="section-title">Distribution & Vulnerability Summaries</h2>
        <div className="visuals-grid">
          {/* Chart 1: Risk Level Distribution */}
          <div className="panel visual-panel">
            <div className="panel-header">Risk-Level Distribution</div>
            <p className="visual-desc">
              Segmentation based on hybrid ring score thresholds (High ≥ 0.80, Medium 0.50–0.79, Low &lt; 0.50).
            </p>

            <div className="svg-chart-container" role="img" aria-label="Risk-level distribution bar chart">
              <svg className="native-svg-chart" viewBox="0 0 380 140" width="100%" height="140">
                <title>Risk-Level Distribution</title>
                <desc>
                  High risk: {analysis.highRiskRings}, Medium risk: {analysis.mediumRiskRings}, Low risk: {analysis.lowRiskRings}.
                </desc>
                {/* Bars */}
                {[
                  {
                    key: 'high',
                    label: 'High Risk (≥ 0.80)',
                    count: analysis.highRiskRings,
                    color: 'var(--score-high)',
                    y: 15,
                  },
                  {
                    key: 'medium',
                    label: 'Medium Risk (0.50–0.79)',
                    count: analysis.mediumRiskRings,
                    color: 'var(--score-medium)',
                    y: 55,
                  },
                  {
                    key: 'low',
                    label: 'Low Risk (< 0.50)',
                    count: analysis.lowRiskRings,
                    color: 'var(--score-low)',
                    y: 95,
                  },
                ].map(({ key, label, count, color, y }) => {
                  const pct = analysis.totalRings > 0 ? (count / analysis.totalRings) * 100 : 0;
                  const barWidth = Math.max((pct / 100) * 200, count > 0 ? 4 : 0);
                  const isHovered = activeHoverBar === `risk-${key}`;

                  return (
                    <g
                      key={key}
                      className="svg-bar-group"
                      onMouseEnter={() => setActiveHoverBar(`risk-${key}`)}
                      onMouseLeave={() => setActiveHoverBar(null)}
                      tabIndex={0}
                      role="graphics-symbol"
                      aria-label={`${label}: ${count} rings (${pct.toFixed(1)}%)`}
                    >
                      <text x="0" y={y + 14} className="svg-label-text">
                        {label}
                      </text>
                      {/* Track */}
                      <rect x="150" y={y} width="160" height="18" rx="4" className="svg-bar-track" />
                      {/* Fill */}
                      <rect
                        x="150"
                        y={y}
                        width={barWidth * 0.8}
                        height="18"
                        rx="4"
                        fill={color}
                        className={`svg-bar-fill ${isHovered ? 'svg-bar-fill--hovered' : ''}`}
                      />
                      {/* Count & % */}
                      <text x="320" y={y + 14} className="svg-value-text mono">
                        {count} ({pct.toFixed(0)}%)
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <div className="chart-legend" aria-hidden="true">
              <span className="legend-item"><span className="legend-swatch swatch-high" /> High Risk</span>
              <span className="legend-item"><span className="legend-swatch swatch-med" /> Medium</span>
              <span className="legend-item"><span className="legend-swatch swatch-low" /> Low</span>
            </div>
          </div>

          {/* Chart 2: Review Status Distribution */}
          <div className="panel visual-panel">
            <div className="panel-header">Investigation Queue Status</div>
            <p className="visual-desc">
              Current lifecycle status across all detected abuse ring cases.
            </p>

            <div className="svg-chart-container" role="img" aria-label="Investigation status breakdown">
              <svg className="native-svg-chart" viewBox="0 0 380 160" width="100%" height="160">
                <title>Investigation Queue Status</title>
                <desc>
                  New: {analysis.newCases}, Reviewing: {analysis.reviewingCases}, Confirmed: {analysis.confirmedCases}, Dismissed: {analysis.dismissedCases}.
                </desc>
                {[
                  { key: 'new', label: 'New (Pending)', count: analysis.newCases, color: 'var(--status-new)', y: 10 },
                  { key: 'reviewing', label: 'Under Review', count: analysis.reviewingCases, color: 'var(--status-reviewing)', y: 46 },
                  { key: 'confirmed', label: 'Confirmed Abuse', count: analysis.confirmedCases, color: 'var(--status-confirmed)', y: 82 },
                  { key: 'dismissed', label: 'Dismissed', count: analysis.dismissedCases, color: 'var(--status-dismissed)', y: 118 },
                ].map(({ key, label, count, color, y }) => {
                  const pct = analysis.totalRings > 0 ? (count / analysis.totalRings) * 100 : 0;
                  const barWidth = Math.max((pct / 100) * 160, count > 0 ? 4 : 0);
                  const isHovered = activeHoverBar === `status-${key}`;

                  return (
                    <g
                      key={key}
                      className="svg-bar-group"
                      onMouseEnter={() => setActiveHoverBar(`status-${key}`)}
                      onMouseLeave={() => setActiveHoverBar(null)}
                      tabIndex={0}
                      role="graphics-symbol"
                      aria-label={`${label}: ${count} cases (${pct.toFixed(1)}%)`}
                    >
                      <text x="0" y={y + 14} className="svg-label-text">
                        {label}
                      </text>
                      <rect x="130" y={y} width="160" height="18" rx="4" className="svg-bar-track" />
                      <rect
                        x="130"
                        y={y}
                        width={barWidth}
                        height="18"
                        rx="4"
                        fill={color}
                        className={`svg-bar-fill ${isHovered ? 'svg-bar-fill--hovered' : ''}`}
                      />
                      <text x="300" y={y + 14} className="svg-value-text mono">
                        {count} ({pct.toFixed(0)}%)
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <div className="chart-legend" aria-hidden="true">
              <span className="legend-item"><span className="legend-swatch swatch-new" /> New</span>
              <span className="legend-item"><span className="legend-swatch swatch-reviewing" /> Reviewing</span>
              <span className="legend-item"><span className="legend-swatch swatch-confirmed" /> Confirmed</span>
              <span className="legend-item"><span className="legend-swatch swatch-dismissed" /> Dismissed</span>
            </div>
          </div>

          {/* Chart 3: Detection Resilience Distribution */}
          <div className="panel visual-panel">
            <div className="panel-header">Detection Resilience Distribution</div>
            <p className="visual-desc">
              Minimum accepted shared-entity losses required to leave fewer than half of the ring's accounts connected as one case.
            </p>

            <div className="svg-chart-container" role="img" aria-label="Detection resilience distribution chart">
              {!analysis.resilienceAssessed ? (
                <p className="text-secondary" style={{ padding: '24px 0', textAlign: 'center' }}>
                  Detection Resilience was not assessed for this run.
                </p>
              ) : (
                <svg className="native-svg-chart" viewBox="0 0 380 140" width="100%" height="140">
                  <title>Detection Resilience Distribution</title>
                  <desc>
                    High resilience: {analysis.resilienceMap.high || 0}, Moderate: {analysis.resilienceMap.moderate || 0}, Low: {analysis.resilienceMap.low || 0}.
                  </desc>
                  {[
                    {
                      key: 'high',
                      label: 'High (3+ losses)',
                      count: analysis.resilienceMap.high || 0,
                      color: '#1E3A8A',
                      y: 15,
                    },
                    {
                      key: 'moderate',
                      label: 'Moderate (2 losses)',
                      count: analysis.resilienceMap.moderate || 0,
                      color: '#2563EB',
                      y: 55,
                    },
                    {
                      key: 'low',
                      label: 'Low (1 loss)',
                      count: analysis.resilienceMap.low || 0,
                      color: '#60A5FA',
                      y: 95,
                    },
                  ].map(({ key, label, count, color, y }) => {
                    const pct = analysis.totalRings > 0 ? (count / analysis.totalRings) * 100 : 0;
                    const barWidth = Math.max((pct / 100) * 160, count > 0 ? 4 : 0);
                    const isHovered = activeHoverBar === `resilience-${key}`;

                    return (
                      <g
                        key={key}
                        className="svg-bar-group"
                        onMouseEnter={() => setActiveHoverBar(`resilience-${key}`)}
                        onMouseLeave={() => setActiveHoverBar(null)}
                        tabIndex={0}
                        role="graphics-symbol"
                        aria-label={`${label}: ${count} rings (${pct.toFixed(1)}%)`}
                      >
                        <text x="0" y={y + 14} className="svg-label-text">
                          {label}
                        </text>
                        <rect x="160" y={y} width="150" height="18" rx="4" className="svg-bar-track" />
                        <rect
                          x="160"
                          y={y}
                          width={barWidth}
                          height="18"
                          rx="4"
                          fill={color}
                          className={`svg-bar-fill ${isHovered ? 'svg-bar-fill--hovered' : ''}`}
                        />
                        <text x="320" y={y + 14} className="svg-value-text mono">
                          {count} ({pct.toFixed(0)}%)
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
            {analysis.resilienceAssessed && (
              <div className="chart-legend" aria-hidden="true">
                <span className="legend-item"><span className="legend-swatch" style={{ background: '#1E3A8A' }} /> High (Dense)</span>
                <span className="legend-item"><span className="legend-swatch" style={{ background: '#2563EB' }} /> Moderate</span>
                <span className="legend-item"><span className="legend-swatch" style={{ background: '#60A5FA' }} /> Low</span>
              </div>
            )}
          </div>

          {/* Chart 4: Most Common Shared Entity Types */}
          <div className="panel visual-panel">
            <div className="panel-header">Shared Entity Types (Signal Frequency)</div>
            <p className="visual-desc">
              Number of rings connected via each identifier category.
            </p>

            <div className="svg-chart-container" role="img" aria-label="Shared entity types frequency">
              {Object.keys(analysis.sharedEntityCounts).length === 0 ? (
                <p className="text-muted" style={{ padding: '24px 0' }}>No shared entities identified in current run.</p>
              ) : (
                <svg className="native-svg-chart" viewBox="0 0 380 140" width="100%" height="140">
                  <title>Shared Entity Types Frequency</title>
                  {Object.entries(analysis.sharedEntityCounts)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 3)
                    .map(([entKey, count], idx) => {
                      const y = 15 + idx * 40;
                      const pct = analysis.totalRings > 0 ? (count / analysis.totalRings) * 100 : 0;
                      const barWidth = Math.max((pct / 100) * 160, count > 0 ? 4 : 0);
                      const isHovered = activeHoverBar === `entity-${entKey}`;

                      return (
                        <g
                          key={entKey}
                          className="svg-bar-group"
                          onMouseEnter={() => setActiveHoverBar(`entity-${entKey}`)}
                          onMouseLeave={() => setActiveHoverBar(null)}
                          tabIndex={0}
                          role="graphics-symbol"
                          aria-label={`${formatEntityType(entKey)}: in ${count} rings (${pct.toFixed(1)}%)`}
                        >
                          <text x="0" y={y + 14} className="svg-label-text">
                            {formatEntityType(entKey)}
                          </text>
                          <rect x="150" y={y} width="160" height="18" rx="4" className="svg-bar-track" />
                          <rect
                            x="150"
                            y={y}
                            width={barWidth}
                            height="18"
                            rx="4"
                            fill="var(--accent-blue)"
                            className={`svg-bar-fill ${isHovered ? 'svg-bar-fill--hovered' : ''}`}
                          />
                          <text x="320" y={y + 14} className="svg-value-text mono">
                            {count} ({pct.toFixed(0)}%)
                          </text>
                        </g>
                      );
                    })}
                </svg>
              )}
            </div>
            <div className="chart-legend" aria-hidden="true">
              <span className="legend-item"><span className="legend-swatch" style={{ background: 'var(--accent-blue)' }} /> Shared Connection Signal</span>
            </div>
          </div>

          {/* Chart 5: Most Common Critical Entity Types */}
          <div className="panel visual-panel visual-panel--wide">
            <div className="panel-header">Critical Shared Signals (Minimum Evidence Losses)</div>
            <p className="visual-desc">
              Shared evidence categories that appear in every minimum evidence-loss cut required to leave fewer than half of the accounts connected as one case.
            </p>

            <div className="svg-chart-container" role="img" aria-label="Critical evidence types frequency">
              {!analysis.resilienceAssessed ? (
                <p className="text-secondary" style={{ padding: '24px 0', textAlign: 'center' }}>
                  Detection Resilience was not assessed for this run.
                </p>
              ) : Object.keys(analysis.criticalEntityCounts).length === 0 ? (
                <div className="critical-empty-state">
                  <p className="text-secondary" style={{ padding: '16px 0', textAlign: 'center' }}>
                    No single signal type appears across all minimum evidence-loss cuts for these rings.
                  </p>
                </div>
              ) : (
                <svg className="native-svg-chart" viewBox="0 0 780 120" width="100%" height="120">
                  <title>Critical Entity Types Frequency</title>
                  {Object.entries(analysis.criticalEntityCounts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([critKey, count], idx) => {
                      const y = 15 + idx * 36;
                      const pct = analysis.totalRings > 0 ? (count / analysis.totalRings) * 100 : 0;
                      const barWidth = Math.max((pct / 100) * 380, count > 0 ? 6 : 0);
                      const isHovered = activeHoverBar === `critical-${critKey}`;

                      return (
                        <g
                          key={critKey}
                          className="svg-bar-group"
                          onMouseEnter={() => setActiveHoverBar(`critical-${critKey}`)}
                          onMouseLeave={() => setActiveHoverBar(null)}
                          tabIndex={0}
                          role="graphics-symbol"
                          aria-label={`${formatEntityType(critKey)}: critical in ${count} rings (${pct.toFixed(1)}%)`}
                        >
                          <text x="0" y={y + 14} className="svg-label-text">
                            {formatEntityType(critKey)}
                          </text>
                          <rect x="220" y={y} width="400" height="18" rx="4" className="svg-bar-track" />
                          <rect
                            x="220"
                            y={y}
                            width={barWidth}
                            height="18"
                            rx="4"
                            fill="#E11D48"
                            className={`svg-bar-fill ${isHovered ? 'svg-bar-fill--hovered' : ''}`}
                          />
                          <text x="630" y={y + 14} className="svg-value-text mono">
                            {count} rings ({pct.toFixed(1)}% of all rings)
                          </text>
                        </g>
                      );
                    })}
                </svg>
              )}
            </div>
            {analysis.resilienceAssessed && Object.keys(analysis.criticalEntityCounts).length > 0 && (
              <div className="chart-legend" aria-hidden="true">
                <span className="legend-item"><span className="legend-swatch" style={{ background: '#E11D48' }} /> Critical Shared Signal</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ */}
      {/*  Priority Cases (Interactive Ranked Rings Table)              */}
      {/* ------------------------------------------------------------ */}
      <section className="report-section" aria-labelledby="priority-heading">
        <div className="panel priority-panel">
          <div className="priority-panel-header">
            <div>
              <div className="panel-header">Investigative Triage Queue</div>
              <h2 id="priority-heading" className="section-title">Priority Cases</h2>
              <p className="text-secondary">
                Rings ranked by hybrid multi-signal score. Filter by risk severity or status to target queues.
              </p>
            </div>

            {/* Filter Controls */}
            <div className="priority-filters" aria-label="Filter priority cases">
              <div className="filter-group">
                <label htmlFor="filter-risk" className="filter-label">Risk Level:</label>
                <select
                  id="filter-risk"
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value as 'all' | 'high' | 'medium' | 'low')}
                >
                  <option value="all">All Risks ({data.rings.length})</option>
                  <option value="high">High Risk (≥0.80)</option>
                  <option value="medium">Medium Risk (0.50–0.79)</option>
                  <option value="low">Low Risk (&lt;0.50)</option>
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="filter-status" className="filter-label">Review Status:</label>
                <select
                  id="filter-status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as 'all' | ReviewStatus)}
                >
                  <option value="all">All Statuses</option>
                  <option value="new">New</option>
                  <option value="reviewing">Reviewing</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="dismissed">Dismissed</option>
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="filter-limit" className="filter-label">Show:</label>
                <select
                  id="filter-limit"
                  value={displayLimit}
                  onChange={(e) => setDisplayLimit(Number(e.target.value) as 10 | 20 | 0)}
                >
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                  <option value={0}>All Matching ({filteredRings.length})</option>
                </select>
              </div>
            </div>
          </div>

          <div className="table-responsive">
            <table className="priority-table" aria-label="Priority abuse rings table">
              <thead>
                <tr>
                  <th scope="col" style={{ width: '45px' }}>Rank</th>
                  <th scope="col">Ring ID</th>
                  <th scope="col">Risk Level</th>
                  <th scope="col">Score</th>
                  <th scope="col">Review Status</th>
                  <th scope="col">Members</th>
                  <th scope="col">Shared Entities</th>
                  <th scope="col">Resilience</th>
                  <th scope="col">Critical Evidence Types</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {displayedRings.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="empty-table-cell text-muted">
                      No rings match the selected filter combination.
                    </td>
                  </tr>
                ) : (
                  displayedRings.map((r: ReportRow) => {
                    const scorePct = Math.round(r.ring_score * 100);
                    const riskClass =
                      r.risk_level === 'high'
                        ? 'status-confirmed'
                        : r.risk_level === 'medium'
                        ? 'status-reviewing'
                        : 'status-new';

                    return (
                      <tr key={r.ring_id}>
                        <td className="mono text-muted">#{r.rank}</td>
                        <td>
                          <Link to={`/rings/${r.ring_id}`} className="ring-id-link mono font-semibold">
                            {r.ring_id}
                          </Link>
                        </td>
                        <td>
                          <span className={`status-badge ${riskClass}`}>
                            {r.risk_level}
                          </span>
                        </td>
                        <td>
                          <div className="risk-score">
                            <span className="mono font-semibold">{r.ring_score.toFixed(3)}</span>
                            <div className="score-bar" aria-hidden="true">
                              <div className="score-bar-fill">
                                <div
                                  className={`score-bar-fill-inner score-dist-bar--${r.risk_level}`}
                                  style={{ width: `${scorePct}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`status-badge status-${r.review_status}`}>
                            {r.review_status}
                          </span>
                        </td>
                        <td className="mono">{r.member_count}</td>
                        <td className="mono">{r.shared_entity_count}</td>
                        <td>
                          {r.detection_resilience ? (
                            <span className={`resilience-pill resilience-${r.detection_resilience}`}>
                              {r.detection_resilience}
                              {r.min_entity_removals != null && (
                                <span className="mono" style={{ marginLeft: 3 }}>
                                  ({r.min_entity_removals} rem)
                                </span>
                              )}
                            </span>
                          ) : (
                            <span className="text-muted">Unassessed</span>
                          )}
                        </td>
                        <td>
                          {r.critical_entity_types && r.critical_entity_types.length > 0 ? (
                            <div className="tags-flex">
                              {r.critical_entity_types.map((c) => (
                                <span key={c} className="reason-pill reason-pill--critical">
                                  {formatEntityType(c)}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-muted" style={{ fontSize: '0.78rem' }}>
                              {analysis.resilienceAssessed ? 'None' : 'Unassessed'}
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <Link to={`/rings/${r.ring_id}`} className="btn-inspect">
                            Inspect →
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="priority-table-footer">
            <span className="text-secondary">
              Showing {displayedRings.length} of {filteredRings.length} matching rings
              {displayLimit > 0 && filteredRings.length > displayLimit && ' (limited view)'}
            </span>
            {displayLimit > 0 && filteredRings.length > displayLimit && (
              <button
                className="btn btn-show-all"
                onClick={() => setDisplayLimit(0)}
              >
                View all {filteredRings.length} matching rings
              </button>
            )}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ */}
      {/*  Methodology & Decision Support Section (Expandable)         */}
      {/* ------------------------------------------------------------ */}
      <section className="report-section" aria-labelledby="methodology-heading">
        <div className="panel methodology-panel">
          <button
            id="methodology-heading"
            className="methodology-accordion-trigger"
            onClick={() => setMethodologyOpen(!methodologyOpen)}
            aria-expanded={methodologyOpen}
            aria-controls="methodology-content"
          >
            <div className="methodology-trigger-text">
              <span className="panel-header" style={{ marginBottom: 2 }}>System Reference & Governance</span>
              <h2 className="section-title" style={{ margin: 0, fontSize: '1.15rem' }}>
                Detection Methodology & Score Interpretation
              </h2>
            </div>
            <span className="accordion-icon" aria-hidden="true">
              {methodologyOpen ? '−' : '+'}
            </span>
          </button>

          {methodologyOpen && (
            <div id="methodology-content" className="methodology-content">
              <div className="methodology-grid">
                <div className="methodology-item">
                  <div className="methodology-badge">1</div>
                  <div>
                    <h3>Behavioural Feature Scoring</h3>
                    <p>
                      Individual accounts are evaluated with a supervised classifier assessing account
                      creation velocity, transaction burst cadence, promotion reuse intensity, and
                      identity similarity heuristics. Scores range from 0 to 1, pinpointing synthetic accounts.
                    </p>
                  </div>
                </div>

                <div className="methodology-item">
                  <div className="methodology-badge">2</div>
                  <div>
                    <h3>Relationship & Graph Analysis</h3>
                    <p>
                      Accounts are connected through shared identifiers (IP addresses, device fingerprints,
                      payment instruments) into an undirected bipartite graph. Connected components define
                      potential abuse rings operating across shared technical assets.
                    </p>
                  </div>
                </div>

                <div className="methodology-item">
                  <div className="methodology-badge">3</div>
                  <div>
                    <h3>Hybrid Ring Ranking</h3>
                    <p>
                      Ring risk scores synthesize six weighted dimensions defined in the detection model:
                      mean member ML score (35%), maximum member ML score (15%), temporal concentration (15%),
                      shared-entity strength (15%), graph density (10%), and promotion concentration (10%).
                      This balances individual account anomalies with structural coordination strength.
                    </p>
                  </div>
                </div>

                <div className="methodology-item">
                  <div className="methodology-badge">4</div>
                  <div>
                    <h3>Detection Resilience</h3>
                    <p>
                      Evaluates structural stability by calculating the minimum accepted shared-entity
                      losses required to leave fewer than half of the ring's accounts connected as one case.
                      Critical evidence types are shared signal categories that appear in every minimum
                      evidence-loss cut. Rings with low resilience depend on a small minimum evidence-loss set,
                      whereas high-resilience rings maintain redundant multi-path connectivity.
                    </p>
                  </div>
                </div>

                <div className="methodology-item">
                  <div className="methodology-badge">5</div>
                  <div>
                    <h3>Ranking Score vs. Probability</h3>
                    <p>
                      The composite ring score is a normalized ordinal ranking score (0.00 to 1.00)
                      designed to prioritize review queues. It is not an absolute Bayesian probability
                      of fraud.
                    </p>
                  </div>
                </div>

                <div className="methodology-item">
                  <div className="methodology-badge">6</div>
                  <div>
                    <h3>Human-in-the-Loop Decision Support</h3>
                    <p>
                      Legitimate shared environments (e.g. university campuses, shared office Wi-Fi, family cards)
                      can form graph connections. Automated hard-blocks trigger catastrophic false positives.
                      This workbench provides comprehensive evidentiary trails to support human decisions.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
