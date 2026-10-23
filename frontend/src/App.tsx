import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import District from './pages/District'
import Explore from './pages/Explore'
import Home from './pages/Home'
import Insights from './pages/Insights'
import Methods from './pages/Methods'
import Priorities from './pages/Priorities'
import Reports from './pages/Reports'
import Simulator from './pages/Simulator'

function NotFound() {
  return (
    <section className="section">
      <div className="container empty">
        <h2>Page not found</h2>
        <p><Link to="/">Back to home</Link></p>
      </div>
    </section>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="explore" element={<Explore />} />
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="districts/:name" element={<District />} />
          <Route path="insights" element={<Insights />} />
          <Route path="priorities" element={<Priorities />} />
          <Route path="simulator" element={<Simulator />} />
          <Route path="reports" element={<Reports />} />
          <Route path="methods" element={<Methods />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
