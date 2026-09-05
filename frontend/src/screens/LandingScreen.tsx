import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { warmApi } from '../api';
import './LandingScreen.css';

/* ================================================================== */
/*  Constants                                                          */
/* ================================================================== */

const GITHUB_URL = 'https://github.com/anubhavi-hoon/razorpay-abuse-ring-detector';

const PIPELINE_STEPS = [
  {
    num: 1,
    title: 'Observe behavior',
    desc: 'Build deterministic account features from signup, transaction, promotion, failure, refund, and timing activity.',
  },
  {
    num: 2,
    title: 'Score accounts',
    desc: 'Use an interpretable logistic-regression model to prioritize suspicious behavioral patterns.',
  },
  {
    num: 3,
    title: 'Connect relationships',
    desc: 'Build a graph of accounts sharing devices, IPs, payment instruments, identifiers, merchants, and promotions.',
  },
  {
    num: 4,
    title: 'Investigate rings',
    desc: 'Rank coordinated groups and show analysts the evidence, members, reasons, and review workflow.',
  },
] as const;

const DEMO_RESULTS = [
  { value: '2,000', label: 'Accounts analyzed' },
  { value: '10,000', label: 'Transactions processed' },
  { value: '15', label: 'Planted abuse rings' },
  { value: '208', label: 'Candidate components' },
  { value: '15 / 15', label: 'Rings in top 20' },
  { value: '0.28s', label: 'Pipeline runtime' },
] as const;

const TECH_NODES = [
  'CSV data',
  'Feature engineering',
  'Logistic regression',
  'NetworkX analysis',
  'Hybrid ranking',
  'FastAPI + PostgreSQL',
  'React UI',
] as const;

/* ================================================================== */
/*  Hero SVG — Interactive relationship illustration                   */
/* ================================================================== */

interface HeroNode {
  id: string;
  label: string;
  sublabel: string;
  x: number;
  y: number;
  w: number;
  h: number;
  type: 'account' | 'shared' | 'promotion';
}

interface HeroEdge {
  from: string;
  to: string;
}

const HERO_NODES: HeroNode[] = [
  { id: 'a1', label: 'Account A', sublabel: 'Created 2 weeks ago', x: 20, y: 30, w: 110, h: 44, type: 'account' },
  { id: 'a2', label: 'Account B', sublabel: 'Created 2 weeks ago', x: 20, y: 100, w: 110, h: 44, type: 'account' },
  { id: 'a3', label: 'Account C', sublabel: 'Created 12 days ago', x: 20, y: 170, w: 110, h: 44, type: 'account' },
  { id: 's1', label: 'Shared device', sublabel: 'dev_0f8a…3e1d', x: 210, y: 50, w: 120, h: 44, type: 'shared' },
  { id: 's2', label: 'Shared payment', sublabel: 'pay_4b2c…7a9f', x: 210, y: 130, w: 120, h: 44, type: 'shared' },
  { id: 'p1', label: 'Promotion 01', sublabel: 'WELCOME_50', x: 370, y: 50, w: 110, h: 44, type: 'promotion' },
  { id: 'p2', label: 'Shared IP', sublabel: '192.168.x.x', x: 370, y: 130, w: 110, h: 44, type: 'promotion' },
];

const HERO_EDGES: HeroEdge[] = [
  { from: 'a1', to: 's1' },
  { from: 'a2', to: 's1' },
  { from: 'a2', to: 's2' },
  { from: 'a3', to: 's2' },
  { from: 'a1', to: 'p1' },
  { from: 'a2', to: 'p1' },
  { from: 'a3', to: 'p2' },
  { from: 'a1', to: 'p2' },
];

const NODE_TOOLTIPS: Record<string, string> = {
  a1: 'Account A appears legitimate individually — few transactions, no obvious flags.',
  a2: 'Account B shares infrastructure with both A and C, connecting them into a ring.',
  a3: 'Account C reuses the same payment method and IP, revealing coordination.',
  s1: 'This device fingerprint was used by multiple accounts during registration.',
  s2: 'This payment instrument was reused across accounts in the group.',
  p1: 'All three accounts claimed the same welcome promotion.',
  p2: 'Multiple accounts accessed the platform from the same IP address.',
};

function getNodeCenter(node: HeroNode): { cx: number; cy: number } {
  return { cx: node.x + node.w / 2, cy: node.y + node.h / 2 };
}

function getConnectedIds(nodeId: string): Set<string> {
  const connected = new Set<string>();
  connected.add(nodeId);
  for (const edge of HERO_EDGES) {
    if (edge.from === nodeId) connected.add(edge.to);
    if (edge.to === nodeId) connected.add(edge.from);
  }
  return connected;
}

function HeroIllustration() {
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [animated, setAnimated] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    // trigger draw-in animation on mount
    const t = setTimeout(() => setAnimated(true), 100);
    return () => clearTimeout(t);
  }, []);

  const connectedSet = activeNode ? getConnectedIds(activeNode) : null;

  function isEdgeHighlighted(edge: HeroEdge): boolean {
    if (!activeNode) return false;
    return edge.from === activeNode || edge.to === activeNode;
  }

  function isEdgeDimmed(edge: HeroEdge): boolean {
    if (!activeNode) return false;
    return !isEdgeHighlighted(edge);
  }

  function isNodeDimmed(id: string): boolean {
    if (!connectedSet) return false;
    return !connectedSet.has(id);
  }

  function handleNodeInteraction(id: string) {
    setActiveNode((prev) => (prev === id ? null : id));
  }

  function handleKeyDown(e: React.KeyboardEvent, id: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleNodeInteraction(id);
    }
    if (e.key === 'Escape') {
      setActiveNode(null);
    }
  }

  const activeNodeData = activeNode
    ? HERO_NODES.find((n) => n.id === activeNode)
    : null;

  return (
    <div
      className={`hero-illustration${animated ? ' animated' : ''}`}
      style={{ position: 'relative' }}
    >
      <svg
        ref={svgRef}
        viewBox="0 0 500 230"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="Illustration showing how multiple accounts connect through shared devices, payment methods, and promotions to form an abuse ring"
      >
        {/* Edges */}
        <g aria-hidden="true">
          {HERO_EDGES.map((edge) => {
            const from = getNodeCenter(
              HERO_NODES.find((n) => n.id === edge.from)!,
            );
            const to = getNodeCenter(
              HERO_NODES.find((n) => n.id === edge.to)!,
            );
            const dx = (to.cx - from.cx) * 0.4;
            const pathD = `M ${from.cx} ${from.cy} C ${from.cx + dx} ${from.cy}, ${to.cx - dx} ${to.cy}, ${to.cx} ${to.cy}`;
            const pathLength = 300; // approximate
            return (
              <path
                key={`${edge.from}-${edge.to}`}
                className={`hero-edge${isEdgeHighlighted(edge) ? ' highlighted' : ''}${isEdgeDimmed(edge) ? ' dimmed' : ''}`}
                d={pathD}
                style={
                  { '--path-length': pathLength } as React.CSSProperties
                }
              />
            );
          })}
        </g>
        {/* Nodes */}
        {HERO_NODES.map((node) => {
          const iconChar =
            node.type === 'account'
              ? '◉'
              : node.type === 'shared'
                ? '⬡'
                : '▣';
          return (
            <g
              key={node.id}
              className={`hero-node${activeNode === node.id ? ' active' : ''}${isNodeDimmed(node.id) ? ' dimmed' : ''}`}
              tabIndex={0}
              role="button"
              aria-label={`${node.label}: ${NODE_TOOLTIPS[node.id]}`}
              aria-pressed={activeNode === node.id}
              onMouseEnter={() => setActiveNode(node.id)}
              onMouseLeave={() => setActiveNode(null)}
              onFocus={() => setActiveNode(node.id)}
              onBlur={() => setActiveNode(null)}
              onClick={() => handleNodeInteraction(node.id)}
              onKeyDown={(e) => handleKeyDown(e, node.id)}
            >
              <rect
                className="hero-node-rect"
                x={node.x}
                y={node.y}
                width={node.w}
                height={node.h}
              />
              <text className="hero-node-icon" x={node.x + 10} y={node.y + 26}>
                {iconChar}
              </text>
              <text
                className="hero-node-label"
                x={node.x + 26}
                y={node.y + 20}
              >
                {node.label}
              </text>
              <text
                className="hero-node-sublabel"
                x={node.x + 26}
                y={node.y + 34}
              >
                {node.sublabel}
              </text>
            </g>
          );
        })}
      </svg>
      {/* Tooltip */}
      {activeNode && activeNodeData && (
        <div
          className="hero-tooltip"
          style={{
            left: Math.min(activeNodeData.x + activeNodeData.w / 2, 340),
            top: activeNodeData.y + activeNodeData.h + 12,
          }}
          role="tooltip"
        >
          {NODE_TOOLTIPS[activeNode]}
        </div>
      )}
    </div>
  );
}

/* ================================================================== */
/*  Walkthrough browser-frame previews                                 */
/* ================================================================== */

function WalkthroughPreview({
  url,
  children,
}: {
  url: string;
  children: React.ReactNode;
}) {
  return (
    <div className="landing-browser-frame">
      <div className="landing-browser-bar" aria-hidden="true">
        <span className="landing-browser-dot" />
        <span className="landing-browser-dot" />
        <span className="landing-browser-dot" />
        <span className="landing-browser-url">{url}</span>
      </div>
      <div className="landing-browser-content">{children}</div>
    </div>
  );
}

/* ================================================================== */
/*  Inline SVG icons                                                   */
/* ================================================================== */

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 9l3 3 7-7" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M9 6v4M9 13h.01" />
      <circle cx="9" cy="9" r="7" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 2L3 5v4c0 3.5 2.5 6.5 6 7.5 3.5-1 6-4 6-7.5V5L9 2z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

/* ================================================================== */
/*  Pipeline step icons                                                */
/* ================================================================== */

function PipelineIcon({ step }: { step: number }) {
  const icons = [
    // 1: Observe — eye
    <svg key="1" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <path d="M1 10s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z" />
      <circle cx="10" cy="10" r="3" />
    </svg>,
    // 2: Score — bar chart
    <svg key="2" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <rect x="3" y="10" width="3" height="7" rx="1" />
      <rect x="8.5" y="6" width="3" height="11" rx="1" />
      <rect x="14" y="3" width="3" height="14" rx="1" />
    </svg>,
    // 3: Connect — network
    <svg key="3" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="10" cy="5" r="2" />
      <circle cx="5" cy="15" r="2" />
      <circle cx="15" cy="15" r="2" />
      <path d="M10 7v3M8.5 11.5L6.5 13.5M11.5 11.5l2 2" />
    </svg>,
    // 4: Investigate — magnifier
    <svg key="4" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="M12.5 12.5L17 17" />
    </svg>,
  ];
  return icons[step - 1] ?? null;
}

/* ================================================================== */
/*  Landing navigation                                                 */
/* ================================================================== */

function LandingNav() {
  const [menuOpen, setMenuOpen] = useState(false);

  const scrollTo = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, targetId: string) => {
      e.preventDefault();
      setMenuOpen(false);
      const el = document.getElementById(targetId);
      if (el) {
        const prefersReduced = window.matchMedia(
          '(prefers-reduced-motion: reduce)',
        ).matches;
        el.scrollIntoView({
          behavior: prefersReduced ? 'instant' : 'smooth',
        });
      }
    },
    [],
  );

  return (
    <nav className="landing-nav" aria-label="Landing page">
      <div className="landing-nav-inner">
        <a href="#/" className="landing-nav-brand">
          <span className="landing-nav-mark" aria-hidden="true">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="#fff"
              strokeWidth="1.5"
            >
              <circle cx="5" cy="5" r="3" />
              <circle cx="11" cy="11" r="3" />
              <path d="M7 7l2 2" strokeLinecap="round" />
            </svg>
          </span>
          <span className="landing-nav-brand-text">SybilTrace</span>
        </a>

        <ul className="landing-nav-links">
          <li>
            <a href="#problem" onClick={(e) => scrollTo(e, 'problem')}>
              Problem
            </a>
          </li>
          <li>
            <a href="#how-it-works" onClick={(e) => scrollTo(e, 'how-it-works')}>
              How it works
            </a>
          </li>
          <li>
            <a href="#investigation" onClick={(e) => scrollTo(e, 'investigation')}>
              Investigation
            </a>
          </li>
          <li>
            <a href="#technology" onClick={(e) => scrollTo(e, 'technology')}>
              Technology
            </a>
          </li>
        </ul>

        <div className="landing-nav-actions">
          <a
            href={GITHUB_URL}
            className="landing-nav-github"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View source on GitHub"
          >
            <GitHubIcon />
          </a>
          <Link to="/dashboard" className="landing-btn-primary">
            Open live demo
          </Link>
        </div>

        {/* Mobile toggle */}
        <button
          className="landing-nav-toggle"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
          aria-controls="landing-mobile-menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {/* Mobile dropdown */}
      <div
        id="landing-mobile-menu"
        className={`landing-nav-mobile${menuOpen ? ' open' : ''}`}
        role="menu"
      >
        <a href="#problem" role="menuitem" onClick={(e) => scrollTo(e, 'problem')}>
          Problem
        </a>
        <a href="#how-it-works" role="menuitem" onClick={(e) => scrollTo(e, 'how-it-works')}>
          How it works
        </a>
        <a href="#investigation" role="menuitem" onClick={(e) => scrollTo(e, 'investigation')}>
          Investigation
        </a>
        <a href="#technology" role="menuitem" onClick={(e) => scrollTo(e, 'technology')}>
          Technology
        </a>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          role="menuitem"
        >
          GitHub
        </a>
        <Link to="/dashboard" role="menuitem" onClick={() => setMenuOpen(false)}>
          Open live demo →
        </Link>
      </div>
    </nav>
  );
}

/* ================================================================== */
/*  Main landing screen                                                */
/* ================================================================== */

export default function LandingScreen() {
  const mainRef = useRef<HTMLDivElement>(null);
  const [warmState, setWarmState] = useState<'idle' | 'preparing' | 'ready' | 'fallback'>('idle');

  /* ---- Silent background warm-up of the cold-start API ---- */
  useEffect(() => {
    let isMounted = true;
    const timer = setTimeout(() => {
      if (isMounted) {
        setWarmState((prev) => (prev === 'idle' ? 'preparing' : prev));
      }
    }, 700);

    warmApi()
      .then(() => {
        if (isMounted) {
          clearTimeout(timer);
          setWarmState('ready');
        }
      })
      .catch(() => {
        if (isMounted) {
          clearTimeout(timer);
          setWarmState('fallback');
        }
      });

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, []);

  /* ---- IntersectionObserver for scroll reveals ---- */
  useEffect(() => {
    const root = mainRef.current;
    if (!root) return;

    const prefersReduced = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches;

    if (prefersReduced) {
      // Show everything immediately
      root
        .querySelectorAll<HTMLElement>('[data-reveal]')
        .forEach((el) => el.classList.add('revealed'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );

    root
      .querySelectorAll<HTMLElement>('[data-reveal]')
      .forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  return (
    <div className="landing" ref={mainRef}>
      {/* Skip link */}
      <a href="#landing-main" className="skip-link">
        Skip to main content
      </a>

      <LandingNav />

      <main id="landing-main">
        {/* ============================================================ */}
        {/*  HERO                                                        */}
        {/* ============================================================ */}
        <section className="landing-hero">
          <div className="landing-inner">
            <div className="landing-hero-grid">
              <div className="landing-hero-copy">
                <p className="landing-hero-eyebrow">
                  Ring-first intelligence for coordinated promotional abuse
                </p>
                <h1>
                  See the ring,{' '}
                  <span style={{ whiteSpace: 'nowrap' }}>
                    not just the risky&nbsp;account.
                  </span>
                </h1>
                <p className="landing-hero-body">
                  SybilTrace combines account behavior with shared
                  devices, networks, payment methods, and promotion activity to
                  surface coordinated abuse as explainable investigation cases.
                </p>
                <div className="landing-hero-actions">
                  <Link to="/dashboard" className="landing-btn-primary">
                    Open investigation console
                    <span aria-hidden="true">→</span>
                  </Link>
                  <a
                    href="#how-it-works"
                    className="landing-btn-secondary"
                    onClick={(e) => {
                      e.preventDefault();
                      const el = document.getElementById('how-it-works');
                      if (el) {
                        const prefersReduced = window.matchMedia(
                          '(prefers-reduced-motion: reduce)',
                        ).matches;
                        el.scrollIntoView({
                          behavior: prefersReduced ? 'instant' : 'smooth',
                        });
                      }
                    }}
                  >
                    See how detection works
                  </a>
                </div>
                {warmState !== 'idle' && (
                  <div
                    className={`landing-warm-status landing-warm-status--${warmState}`}
                    role="status"
                    aria-live="polite"
                  >
                    <span className="landing-warm-dot" aria-hidden="true" />
                    <span>
                      {warmState === 'preparing' && 'Preparing live demo…'}
                      {warmState === 'ready' && 'Live demo ready'}
                      {warmState === 'fallback' && 'Demo will start when opened'}
                    </span>
                  </div>
                )}
                <p className="landing-hero-disclaimer">
                  Buildathon prototype · Synthetic demonstration data
                </p>
              </div>
              <HeroIllustration />
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  PROBLEM                                                     */}
        {/* ============================================================ */}
        <section
          className="landing-section"
          id="problem"
        >
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">The problem</p>
              <h2 className="landing-section-title">
                Fraud often looks normal one account at a time.
              </h2>
              <p className="landing-section-subtitle">
                Attackers create multiple accounts to repeatedly claim
                promotions. Each account can appear individually legitimate,
                while coordination becomes visible through shared infrastructure
                and synchronized behavior.
              </p>
            </div>

            <div className="landing-problem-grid">
              <div className="landing-problem-panel" data-reveal data-reveal-delay="1">
                <p className="landing-problem-panel-title">
                  <svg className="panel-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
                    <circle cx="10" cy="7" r="4" />
                    <path d="M3 18c0-3.87 3.13-7 7-7s7 3.13 7 7" />
                  </svg>
                  Account-only view
                </p>
                <ul className="landing-problem-items">
                  <li className="landing-problem-item">
                    <CheckIcon className="item-indicator problem-ok" />
                    <span>Normal-looking account with recent signup</span>
                  </li>
                  <li className="landing-problem-item">
                    <CheckIcon className="item-indicator problem-ok" />
                    <span>Small number of transactions</span>
                  </li>
                  <li className="landing-problem-item">
                    <CheckIcon className="item-indicator problem-ok" />
                    <span>One promotion used — within policy</span>
                  </li>
                  <li className="landing-problem-item">
                    <CheckIcon className="item-indicator problem-ok" />
                    <span>No obvious single-account violations</span>
                  </li>
                </ul>
              </div>

              <div className="landing-problem-panel" data-reveal data-reveal-delay="2">
                <p className="landing-problem-panel-title">
                  <svg className="panel-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
                    <circle cx="6" cy="6" r="3" />
                    <circle cx="14" cy="6" r="3" />
                    <circle cx="10" cy="14" r="3" />
                    <path d="M8.5 7.5l2 4M11.5 7.5l-2 4" />
                  </svg>
                  Relationship view
                </p>
                <ul className="landing-problem-items">
                  <li className="landing-problem-item">
                    <AlertIcon className="item-indicator problem-flag" />
                    <span>Reused payment instrument across accounts</span>
                  </li>
                  <li className="landing-problem-item">
                    <AlertIcon className="item-indicator problem-flag" />
                    <span>Shared device fingerprint</span>
                  </li>
                  <li className="landing-problem-item">
                    <AlertIcon className="item-indicator problem-flag" />
                    <span>Shared IP address during registration</span>
                  </li>
                  <li className="landing-problem-item">
                    <AlertIcon className="item-indicator problem-flag" />
                    <span>Accounts created within minutes of each other</span>
                  </li>
                  <li className="landing-problem-item">
                    <AlertIcon className="item-indicator problem-flag" />
                    <span>Same promotion claimed by the entire group</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  HOW IT WORKS                                                */}
        {/* ============================================================ */}
        <section
          className="landing-section"
          id="how-it-works"
        >
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">How it works</p>
              <h2 className="landing-section-title">
                From raw data to ranked investigation cases
              </h2>
              <p className="landing-section-subtitle">
                A four-stage pipeline that combines behavioral scoring with
                relationship analysis to surface coordinated abuse rings.
              </p>
            </div>

            <div className="landing-pipeline">
              {PIPELINE_STEPS.map((step) => (
                <div
                  key={step.num}
                  className="landing-pipeline-step"
                  data-reveal
                  data-reveal-delay={String(step.num)}
                >
                  <div className="landing-pipeline-num">{step.num}</div>
                  <div className="landing-pipeline-icon">
                    <PipelineIcon step={step.num} />
                  </div>
                  <p className="landing-pipeline-title">{step.title}</p>
                  <p className="landing-pipeline-desc">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  INVESTIGATION WALKTHROUGH                                   */}
        {/* ============================================================ */}
        <section
          className="landing-section"
          id="investigation"
        >
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">Investigation workflow</p>
              <h2 className="landing-section-title">
                Follow the evidence from detection to decision
              </h2>
            </div>

            <div className="landing-walkthrough-flow">
              {/* Step 1: Dashboard */}
              <div className="landing-walkthrough-step" data-reveal>
                <div className="landing-walkthrough-copy">
                  <span className="landing-walkthrough-num">Step 01</span>
                  <h3 className="landing-walkthrough-title">
                    Prioritize from the dashboard
                  </h3>
                  <p className="landing-walkthrough-desc">
                    The investigation overview surfaces high-risk rings first.
                    Click through to see run metrics, risk distribution, and the
                    review queue at a glance.
                  </p>
                </div>
                <WalkthroughPreview url="/#/dashboard">
                  <div className="mock-row">
                    <span className="mock-badge mock-badge-high">High risk</span>
                    <span style={{ fontWeight: 500 }}>3 cases need attention</span>
                  </div>
                  <div className="mock-row" style={{ gap: 12 }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--landing-text-muted)' }}>Accounts: 2,000</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--landing-text-muted)' }}>Rings: 208</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--landing-text-muted)' }}>Flagged: 476</span>
                  </div>
                  <div className="mock-bar" style={{ width: '100%' }}>
                    <div className="mock-bar-fill" style={{ width: '65%', background: 'hsl(4, 58%, 70%)' }} />
                  </div>
                </WalkthroughPreview>
              </div>

              {/* Step 2: Ring list */}
              <div className="landing-walkthrough-step" data-reveal>
                <div className="landing-walkthrough-copy">
                  <span className="landing-walkthrough-num">Step 02</span>
                  <h3 className="landing-walkthrough-title">
                    Filter and select a ring
                  </h3>
                  <p className="landing-walkthrough-desc">
                    Browse the ranked ring list. Filter by risk score, review
                    status, promotion, or date to focus your investigation
                    queue.
                  </p>
                </div>
                <WalkthroughPreview url="/#/rings?status=new&min_score=80">
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <span className="mock-badge mock-badge-new">New</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      min_score ≥ 80%
                    </span>
                  </div>
                  <div className="mock-row">
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      ring_ed21b140010d
                    </span>
                    <span className="mock-badge mock-badge-high">94.12%</span>
                  </div>
                  <div className="mock-row">
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      ring_5a9c3f820bd7
                    </span>
                    <span className="mock-badge mock-badge-high">91.47%</span>
                  </div>
                </WalkthroughPreview>
              </div>

              {/* Step 3: Ring detail */}
              <div className="landing-walkthrough-step" data-reveal>
                <div className="landing-walkthrough-copy">
                  <span className="landing-walkthrough-num">Step 03</span>
                  <h3 className="landing-walkthrough-title">
                    Examine evidence and connections
                  </h3>
                  <p className="landing-walkthrough-desc">
                    The ring detail page follows an investigation narrative:
                    identity, why it was flagged, the interactive connection map,
                    supporting metrics, and member evidence.
                  </p>
                </div>
                <WalkthroughPreview url="/#/rings/ring_ed21b140010d">
                  <div className="mock-row" style={{ marginBottom: 4 }}>
                    <span style={{ fontWeight: 600 }}>Ring ring_ed21b14…</span>
                    <span className="mock-badge mock-badge-high">High risk</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--landing-text-muted)', marginBottom: 8 }}>
                    Reason: Shared device · Shared payment · Concentrated promotions
                  </div>
                  <div className="mock-bar" style={{ width: '100%', height: 8 }}>
                    <div className="mock-bar-fill" style={{ width: '94%', background: 'hsl(4, 58%, 60%)', borderRadius: 3 }} />
                  </div>
                </WalkthroughPreview>
              </div>

              {/* Step 4: Review */}
              <div className="landing-walkthrough-step" data-reveal>
                <div className="landing-walkthrough-copy">
                  <span className="landing-walkthrough-num">Step 04</span>
                  <h3 className="landing-walkthrough-title">
                    Make a review decision
                  </h3>
                  <p className="landing-walkthrough-desc">
                    Transition the ring through review statuses: Start Reviewing,
                    Confirm, or Dismiss. Every action is tracked and visible in
                    the investigation queue.
                  </p>
                </div>
                <WalkthroughPreview url="/#/rings/ring_ed21b140010d">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span
                      style={{
                        padding: '4px 12px',
                        background: 'var(--landing-accent)',
                        color: '#fff',
                        borderRadius: 6,
                        fontSize: '0.78rem',
                        fontWeight: 600,
                      }}
                    >
                      Confirm
                    </span>
                    <span
                      style={{
                        padding: '4px 12px',
                        background: 'var(--landing-surface)',
                        border: '1px solid var(--landing-border)',
                        borderRadius: 6,
                        fontSize: '0.78rem',
                        fontWeight: 500,
                      }}
                    >
                      Dismiss
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--landing-text-muted)', marginTop: 8 }}>
                    Status: reviewing → confirmed
                  </div>
                </WalkthroughPreview>
              </div>
            </div>

            <div style={{ textAlign: 'center', marginTop: 40 }} data-reveal>
              <Link to="/rings" className="landing-btn-primary">
                Explore the live case
                <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  WHY THE COMBINATION MATTERS                                 */}
        {/* ============================================================ */}
        <section className="landing-section">
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">Why it matters</p>
              <h2 className="landing-section-title">
                Behavioral scoring and relationship evidence, together
              </h2>
            </div>

            <div className="landing-principles">
              <div className="landing-principle" data-reveal data-reveal-delay="1">
                <div className="landing-principle-icon">
                  <PipelineIcon step={1} />
                </div>
                <p className="landing-principle-title">Behavioral context</p>
                <p className="landing-principle-desc">
                  The model captures promotion velocity, failure and refund
                  behavior, timing patterns, and transaction characteristics —
                  generating interpretable reason codes for each flagged account.
                </p>
              </div>

              <div className="landing-principle" data-reveal data-reveal-delay="2">
                <div className="landing-principle-icon">
                  <PipelineIcon step={3} />
                </div>
                <p className="landing-principle-title">Relationship evidence</p>
                <p className="landing-principle-desc">
                  The graph reveals coordination through reused devices, payment
                  instruments, IP addresses, and merchants — connections that
                  individual account scoring would miss.
                </p>
              </div>

              <div className="landing-principle" data-reveal data-reveal-delay="3">
                <div className="landing-principle-icon">
                  <PipelineIcon step={4} />
                </div>
                <p className="landing-principle-title">Human-readable review</p>
                <p className="landing-principle-desc">
                  Analysts receive ranked cases with reason labels, member
                  evidence, and review controls — not an unexplained automatic
                  block.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  DEMONSTRATION RESULTS                                       */}
        {/* ============================================================ */}
        <section className="landing-section">
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">Validation</p>
              <h2 className="landing-section-title">
                Seeded demonstration results
              </h2>
            </div>

            <div className="landing-results-grid" data-reveal>
              {DEMO_RESULTS.map((r) => (
                <div key={r.label} className="landing-result-card">
                  <p className="landing-result-value">{r.value}</p>
                  <p className="landing-result-label">{r.label}</p>
                </div>
              ))}
            </div>

            <div className="landing-results-disclaimer" data-reveal>
              These results validate the reproducible demo pipeline. They do not
              represent performance on real financial data. The synthetic dataset
              is intentionally separable and requires harder validation on
              production distributions.
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  TECHNOLOGY                                                  */}
        {/* ============================================================ */}
        <section className="landing-section" id="technology">
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">Architecture</p>
              <h2 className="landing-section-title">
                Lightweight, deterministic, explainable
              </h2>
            </div>

            <div className="landing-tech-pipeline" data-reveal>
              {TECH_NODES.map((node, i) => (
                <span key={node}>
                  <span className="landing-tech-node">{node}</span>
                  {i < TECH_NODES.length - 1 && (
                    <span className="landing-tech-arrow" aria-hidden="true">
                      →
                    </span>
                  )}
                </span>
              ))}
            </div>

            <div className="landing-tech-notes" data-reveal>
              <div className="landing-tech-note">
                <CheckIcon className="landing-tech-note-icon" />
                <span>Deterministic and fully reproducible pipeline</span>
              </div>
              <div className="landing-tech-note">
                <CheckIcon className="landing-tech-note-icon" />
                <span>Lightweight enough for modest infrastructure</span>
              </div>
              <div className="landing-tech-note">
                <CheckIcon className="landing-tech-note-icon" />
                <span>Explainable reason codes at every level</span>
              </div>
              <div className="landing-tech-note">
                <CheckIcon className="landing-tech-note-icon" />
                <span>
                  No LLM, RAG, vector database, or graph database required
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  PRIVACY & BOUNDARY                                          */}
        {/* ============================================================ */}
        <section className="landing-section">
          <div className="landing-inner">
            <div className="landing-section-header" data-reveal>
              <p className="landing-section-eyebrow">Trust & boundaries</p>
              <h2 className="landing-section-title">
                Designed for responsible use
              </h2>
            </div>

            <ul className="landing-privacy-list" data-reveal>
              <li className="landing-privacy-item">
                <ShieldIcon className="landing-privacy-icon" />
                <span>
                  The demo uses synthetic or pre-hashed test data. Real personal
                  or payment data should not be uploaded.
                </span>
              </li>
              <li className="landing-privacy-item">
                <ShieldIcon className="landing-privacy-icon" />
                <span>
                  The system supports analyst decisions — it does not
                  automatically block accounts.
                </span>
              </li>
              <li className="landing-privacy-item">
                <ShieldIcon className="landing-privacy-icon" />
                <span>
                  A production version would require security review, privacy
                  compliance, model validation, monitoring, and external
                  fraud-intelligence integrations.
                </span>
              </li>
              <li className="landing-privacy-item">
                <ShieldIcon className="landing-privacy-icon" />
                <span>
                  This is a buildathon prototype demonstrating the approach, not
                  a production-ready product.
                </span>
              </li>
            </ul>
          </div>
        </section>

        {/* ============================================================ */}
        {/*  FINAL CTA                                                   */}
        {/* ============================================================ */}
        <section className="landing-final-cta">
          <div className="landing-inner" data-reveal>
            <h2>Follow the evidence across the whole ring.</h2>
            <p>
              Investigate coordinated abuse with behavioral scoring,
              relationship graphs, and a human-readable review workflow.
            </p>
            <div className="landing-final-cta-actions">
              <Link to="/dashboard" className="landing-btn-primary">
                Open investigation console
                <span aria-hidden="true">→</span>
              </Link>
              <Link to="/rings" className="landing-btn-secondary">
                View ranked rings
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* ============================================================ */}
      {/*  FOOTER                                                      */}
      {/* ============================================================ */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <span className="landing-footer-brand-name">
              SybilTrace
            </span>
            <span className="landing-footer-brand-sub">
              Razorpay Buildathon project
            </span>
          </div>

          <div className="landing-footer-links">
            <Link to="/dashboard">Open demo</Link>
            <Link to="/rings">View rings</Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
          </div>

          <div className="landing-footer-tech">
            React · TypeScript · FastAPI · PostgreSQL · NetworkX · Logistic
            regression · Deterministic pipeline
          </div>

          <div className="landing-footer-disclaimer">
            Independent buildathon prototype using synthetic data. Not an
            official Razorpay product.
          </div>
        </div>
      </footer>
    </div>
  );
}
