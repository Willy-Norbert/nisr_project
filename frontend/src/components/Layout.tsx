import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Icon, Logo } from './Icons'

const NAV: { to: string; label: string }[] = [
  // { to: '/explore', label: 'Ask the data' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/insights', label: 'Insights' },
  { to: '/priorities', label: 'Priorities' },
  { to: '/simulator', label: 'Simulator' },
  { to: '/reports', label: 'Reports' },
]

export default function Layout() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    setOpen(false)
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="app">
      <header className="header">
        <div className="container">
          <Link to="/" aria-label="Analiza home" className="logo-link"><Logo /></Link>
          <button className="nav-toggle" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">
            <Icon name="layers" />
          </button>
          <nav className={`nav${open ? ' open' : ''}`}>
            <NavLink to="/" end className="nav-link" aria-label="Home">
              <Icon name="home" size={16} />
              <span>Home</span>
            </NavLink>
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className="nav-link">
                {n.label}
              </NavLink>
            ))}
            <NavLink to="/methods" className="nav-link">Methods</NavLink>
            <Link to="/explore" className="nav-search-btn" aria-label="Search data">
              <Icon name="search" size={14} />
              <span>Search...</span>
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="footer">
        <div className="container footer-top">
          <div>
            <h4>About</h4>
            <ul>
              <li><Link to="/methods">Data &amp; methodology</Link></li>
              <li><Link to="/methods#sources">Data sources</Link></li>
              <li><Link to="/methods#model">Yield model</Link></li>
              <li><Link to="/methods#catalogue">Indicator catalogue</Link></li>
            </ul>
          </div>
          <div>
            <h4>Explore</h4>
            <ul>
              {/* <li><Link to="/explore">Ask the data</Link></li> */}
              <li><Link to="/dashboard">District dashboard</Link></li>
              <li><Link to="/insights">Key insights</Link></li>
              <li><Link to="/priorities">Priority districts</Link></li>
            </ul>
          </div>
          <div>
            <h4>Tools</h4>
            <ul>
              <li><Link to="/simulator">Yield simulator</Link></li>
              <li><Link to="/reports">Download reports</Link></li>
              <li><a href="/docs" target="_blank" rel="noreferrer">Open API</a></li>
            </ul>
          </div>
          <div>
            <h4>Sources</h4>
            <ul>
              <li><a href="https://microdata.statistics.gov.rw/index.php/catalog" target="_blank" rel="noreferrer">NISR Microdata catalog</a></li>
              <li><a href="https://www.statistics.gov.rw" target="_blank" rel="noreferrer">NISR</a></li>
              <li><a href="https://www.geoboundaries.org" target="_blank" rel="noreferrer">geoBoundaries</a></li>
            </ul>
          </div>
        </div>
        <div className="container footer-bottom">
          <div className="footer-brand">
            <span className="footer-seal">
              <img src="/logo.png" alt="Analiza logo" />
            </span>
            <div>
              <strong>Analiza</strong>
              <span>Built by Team BitBender</span>
              <span>NISR Big Data Hackathon 2026</span>
            </div>
          </div>
          <div className="footer-nisr">
            <a
              href="https://www.statistics.gov.rw"
              target="_blank"
              rel="noreferrer"
              title="National Institute of Statistics of Rwanda (NISR)"
            >
              <img
                src="/nisr-logo.png"
                alt="National Institute of Statistics of Rwanda (NISR)"
                className="nisr-logo-img"
              />
            </a>
          </div>
          <p>
            Data: National Institute of Statistics of Rwanda (NISR), Seasonal Agricultural Survey 2024–2025 and
            Agriculture Household Survey 2024. Aligned with NST2 and Vision 2050 agricultural transformation goals.
          </p>
        </div>
      </footer>
    </div>
  )
}
