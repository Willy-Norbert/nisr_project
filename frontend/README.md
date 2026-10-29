# Analiza - Frontend

React 19 + TypeScript (Vite), Leaflet district maps and Recharts. Design follows the NISR website
(primary blue `#005BAA`, gold accent `#F5B800`, Poppins and Inter).

```powershell
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run build    # frontend/dist, served by the FastAPI backend in production
```

Set `VITE_API_URL` at build time only when the API is hosted on a different origin.

For Vercel, set the project root directory to `frontend`. The included `vercel.json`
rewrites direct requests for client-side routes to `index.html`, so refreshing a page
such as `/dashboard` does not return a 404.

```
src/
  lib/          api client and types, formatting, useApi hook
  components/   Layout, ui primitives, DistrictMap, charts, icons
  pages/        Home, Explore, Dashboard, Insights, Priorities, Simulator, Reports, Methods
  styles/       global.css design system
```
