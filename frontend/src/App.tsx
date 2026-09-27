import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Compare from './pages/Compare'
import Circuits from './pages/Circuits'
import Predictions from './pages/Predictions'
import Analyst from './pages/Analyst'
import ModelPage from './pages/ModelPage'
import NotFound from './pages/NotFound'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/compare', label: 'Compare' },
  { to: '/circuits', label: 'Circuits' },
  { to: '/predictions', label: 'Predictions' },
  { to: '/analyst', label: 'Race Analyst' },
  { to: '/model', label: 'Model' },
]

export default function App() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-surface-0/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-2.5">
            <span aria-hidden="true" className="flex gap-0.5">
              <span className="block h-5 w-1.5 -skew-x-12 rounded-sm bg-accent" />
              <span className="block h-5 w-1.5 -skew-x-12 rounded-sm bg-series-1" />
            </span>
            <div>
              <div className="text-sm font-semibold leading-tight tracking-tight">
                ApexStrategy <span className="text-accent">AI</span>
              </div>
              <div className="text-[11px] leading-tight text-ink-muted">
                Evidence-based F1 race strategy analytics
              </div>
            </div>
          </div>

          <nav className="-mx-1 flex gap-1 overflow-x-auto pb-0.5">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-surface-2 text-ink-primary'
                      : 'text-ink-secondary hover:bg-surface-1 hover:text-ink-primary'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:px-6 sm:py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/circuits" element={<Circuits />} />
          <Route path="/circuits/:ref" element={<Circuits />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/analyst" element={<Analyst />} />
          <Route path="/model" element={<ModelPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <footer className="border-t border-line px-4 py-4 sm:px-6">
        <div className="mx-auto max-w-[1400px] text-xs leading-relaxed text-ink-muted">
          Probabilities shown across this app are model estimates derived from
          historical data — not predictions of what will happen. Historical results,
          qualifying times and pit stops come from the Ergast/Jolpica F1 API.
          ApexStrategy AI is an independent project and is not affiliated with
          Formula 1 or the FIA.
        </div>
      </footer>
    </div>
  )
}
