# Legal Intelligence Terminal — Frontend

A React research workspace for Indian case analysis. The interface is organized around one active matter: add case material once, then move through case facts, precedents, an argument map, outcome analysis, and scenarios.

## What the workspace does

- **Overview:** case composer, analysis progress, and a dashboard of available results.
- **Case facts:** structured parties, legal issues, material facts, statutory references, and relief sought.
- **Precedents:** search results with a source inspector and a query that can be refined independently.
- **Argument map:** an interactive Cytoscape workbench with type filters, node search, focus/zoom tools, weak-claim review queue, relationship inspector, and PNG export. Graph links are generated leads for review, not verified legal conclusions.
- **Outcome analysis:** the returned estimate, factor breakdown, input coverage, and model comparison when the backend supplies one.
- **Scenarios:** browser-side sensitivity controls and session comparisons. These are heuristic adjustments, **not** fresh backend predictions.

The case draft is stored in `sessionStorage` for the current browser session. Analysis sends the material to the configured backend API; do not treat the draft-storage label as a privacy or confidentiality guarantee.

## Local development

From `lit-frontend/`:

```bash
npm install
npm run dev
```

The app runs at `http://localhost:3000`. Start the LIT backend separately on port `8000`; the development default API base is `http://localhost:8000/api/v1`. The endpoint can also be changed in Settings. Without a reachable backend, the empty states remain available but analysis requests cannot complete.

```bash
npm run lint
npm run build
```

## Configuration and deployment

The production default is `https://thebenmerlin-lit-backend.hf.space/api/v1`; local development still uses `http://localhost:8000/api/v1`. `VITE_PUBLIC_API_BASE_URL` takes precedence over the older `VITE_API_BASE_URL` during the Vite build, so the tracked production value wins over a stale Vercel setting. Set `VITE_PUBLIC_API_BASE_URL` in the deployment environment to point at another backend. Clear any old custom URL in Settings to use the deployed default. `vercel.json` provides SPA route rewrites.

## Structure

```text
src/
  components/layout/      Workspace navigation and shell
  components/workspace/   Shared page and workflow components
  pages/                  Seven workspace routes
  workspace/              Active-case state and API orchestration
  lib/api.js              Backend client
  utils/whatIfCalculator.js  Browser-side scenario heuristic
  styles/globals.css      Design system and responsive layout
```

Built with Vite, React, React Router, Cytoscape.js, and Lucide icons.
