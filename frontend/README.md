# SybilTrace — Frontend

Investigation-workbench dashboard for exploring multi-account abuse rings, relationship graphs, account features, and review workflows.

## Prerequisites

- Node.js 20.19 or newer
- Backend API running on `http://127.0.0.1:8000` (see root [`README.md`](../README.md))

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure API base URL (optional):**
   The frontend defaults to `http://127.0.0.1:8000/api/v1` automatically. To override:
   ```bash
   cp .env.example .env
   # Edit VITE_API_BASE_URL in .env if running backend on a different port or host
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```
   The application runs on `http://localhost:3000` (matching the backend's allowed CORS origin).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Starts the Vite development server on port `3000` |
| `npm run build` | Runs TypeScript type check and builds the production bundle in `dist/` |
| `npm run lint` | Runs `oxlint` against all source files |
| `npm run preview` | Previews the production build locally |

## Project Structure

```
frontend/src/
├── api.ts                  # Typed fetch client reading VITE_API_BASE_URL
├── types.ts                # TypeScript interfaces matching docs/openapi.json
├── constants.ts            # Reason-code mappings, review transitions, formatters
├── index.css               # Investigation-workbench design system & tokens
├── App.tsx                 # HashRouter setup & route definitions
├── main.tsx                # React root mount
├── components/
│   ├── Layout.tsx          # Workbench shell (sidebar, breadcrumbs, toasts)
│   ├── Layout.css
│   ├── toastContext.ts     # Toast notification context
│   ├── RelationshipGraph.tsx # Deterministic bipartite native SVG graph
│   └── RelationshipGraph.css
└── screens/
    ├── DashboardScreen.tsx # Run metrics, score distribution, review counts
    ├── RingListScreen.tsx  # Filterable ranked rings table with pagination
    ├── RingDetailScreen.tsx# Ring metrics, SVG graph, member fallback, review actions
    └── AccountDetailScreen.tsx # Identity, ML score, features, ring IDs, transactions
```
