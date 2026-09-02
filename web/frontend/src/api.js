// The /api prefix is a DEV-only alias: the vite proxy rewrites it away
// (vite.config.js — rewrite /api/* → /*). The production backend serves us
// same-origin at root (server.py StaticFiles on :8000) — no prefix there.
// Before this fix the prod build called /api/* → 404 on every endpoint.
export const API_BASE = import.meta.env.DEV ? '/api' : '';
