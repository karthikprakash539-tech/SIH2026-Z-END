# BlockSync Frontend (React/Vite) — Setup

This replaces your old `frontend/index (2).html`. All 6 sections are ported
1:1 (Login, Railway Corridor, Maintenance Defects, Dashboard, AI Plans,
Audit Log), plus a new "Railway Network" graph view placed right under
Login so it's the first thing seen after login.

## Install

From inside this `frontend/` folder:

```
npm install
npm run dev
```

Opens at http://localhost:5173 by default. Make sure your backend is
running on http://127.0.0.1:8000 (unchanged from before — the API base
URL is set in `src/api/client.js`).

## What's new vs. the old single HTML file

- `src/components/NetworkGraph.jsx` — the interactive network view,
  built on `@xyflow/react`. It calls `GET /graph/network`, lays stations
  out left-to-right by BFS layer from the busiest junction (a simple,
  readable schematic layout rather than a physics simulation), and
  colors each section edge by status:
    - red = critical (3+ open defects)
    - amber = attention (open defect or pending block request)
    - dark gray = normal
  Edge thickness scales with traffic_density (trains sharing that
  section). Diamond nodes = junctions (3+ connecting sections), circle
  nodes = regular stations. Click any edge to see its full detail panel
  (distance, traffic density, open defects, pending requests, status).

- Everything else behaves exactly like the old HTML: same login flow,
  same emergency-defect simulate button, same approve/reject actions,
  same admin-only audit log gate.

## Known follow-ups (not done yet, flagging for later)

- Auth token is stored in localStorage (`bs_token`) so it survives a
  page refresh — the old HTML kept it in memory only, this is a small
  upgrade, not a regression.
- The graph layout is deterministic per node id but does NOT persist
  drag positions between reloads — nodes are still `draggable: true`
  for exploration during a demo, but position won't survive a refresh.
  Say the word if you want that persisted (e.g. via localStorage) before
  the demo.
