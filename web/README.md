# web/ — analyst dashboard

React 19 + TypeScript + Vite + Tailwind CSS v4 + React Router, with Recharts for the live latency chart. Full description, page list and how to run it next to the API and the simulator: [README → Dashboard](../README.md#dashboard).

```bash
npm install
cp .env.example .env   # VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY, VITE_API_URL
npm run dev            # http://localhost:5180 (strict port: the API's CORS default)
npm test               # Vitest + React Testing Library
npm run typecheck && npm run lint && npm run build
```

Only public values belong in `.env` here (everything prefixed `VITE_` ends up in the browser). Never put the Supabase secret / service-role key in `web/`; `tests/no-secrets.test.ts` fails if one appears.

| Folder | Contents |
|---|---|
| `src/pages/` | Landing, Login, LiveFeed, Alerts + AlertDetail, ModelSystem, NotFound |
| `src/components/` | Layout (top navigation), Modal, badges, KPI cards, ShapBars, `model/` and `system/` panels |
| `src/hooks/` | Realtime feed and alerts, polling, async loading, count-up |
| `src/lib/` | Supabase client, API client, types, formatting, feed reducer, alert review logic |
| `src/test/` | Test helpers: fake Supabase client, providers, sample data |
| `public/figures/` | Training charts copied from `docs/figures/` |
