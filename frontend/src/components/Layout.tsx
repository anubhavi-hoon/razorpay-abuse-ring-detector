import { useState, useCallback, useEffect } from 'react';
import { NavLink, Link, Outlet, useLocation } from 'react-router-dom';
import { ToastContext } from './toastContext';
import type { Toast } from './toastContext';
import './Layout.css';

/* ------------------------------------------------------------------ */
/*  Breadcrumbs                                                        */
/* ------------------------------------------------------------------ */

function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);

  const crumbs: { label: string; path: string }[] = [
    { label: 'Dashboard', path: '/' },
  ];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const path = '/' + segments.slice(0, i + 1).join('/');

    if (seg === 'dashboard') {
      continue;
    } else if (seg === 'rings') {
      crumbs.push({ label: 'Rings', path: '/rings' });
    } else if (seg === 'accounts') {
      crumbs.push({ label: 'Accounts', path: '/rings' });
    } else {
      // ID segment — truncate for display if long
      const display = seg.length > 20 ? seg.slice(0, 20) + '…' : seg;
      crumbs.push({ label: display, path });
    }
  }

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      {crumbs.map((c, i) => (
        <span key={c.path + '-' + i}>
          {i > 0 && <span className="breadcrumb-sep">/</span>}
          {i === crumbs.length - 1 ? (
            <span className="breadcrumb-current mono">{c.label}</span>
          ) : (
            <Link to={c.path} className="mono">
              {c.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/*  Layout                                                             */
/* ------------------------------------------------------------------ */

let toastCounter = 0;

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: 'success' | 'error') => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  // Close sidebar on navigation
  const location = useLocation();
  useEffect(() => {
    setSidebarOpen(false);
  }, [location]);

  return (
    <ToastContext.Provider value={{ addToast }}>
      <div className="app-layout">
        {/* Mobile hamburger */}
        <button
          className="hamburger"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle navigation"
          aria-expanded={sidebarOpen}
          aria-controls="sidebar-nav-menu"
        >
          <span />
          <span />
          <span />
        </button>

        {/* Sidebar */}
        <aside
          id="sidebar-nav-menu"
          className={`sidebar ${sidebarOpen ? 'sidebar--open' : ''}`}
        >
          <div className="sidebar-title">
            <span className="sidebar-title-text">Abuse Ring Detector</span>
          </div>
          <nav className="sidebar-nav">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'sidebar-link--active' : ''}`
              }
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/rings"
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'sidebar-link--active' : ''}`
              }
            >
              Rings
            </NavLink>
          </nav>
        </aside>

        {/* Overlay for mobile sidebar */}
        {sidebarOpen && (
          <div
            className="sidebar-overlay"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main content */}
        <div className="main-area">
          <header className="topbar">
            <Breadcrumbs />
          </header>
          <main className="content">
            <Outlet />
          </main>
        </div>

        {/* Toasts */}
        <div className="toast-container" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast toast--${t.type}`}>
              {t.message}
            </div>
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
