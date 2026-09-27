import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="card card-pad mx-auto mt-10 max-w-md text-center">
      <p className="text-3xl font-semibold text-ink-primary">404</p>
      <p className="mt-2 text-sm text-ink-secondary">
        That page doesn&rsquo;t exist.
      </p>
      <Link to="/" className="btn-primary mt-4">
        Back to the dashboard
      </Link>
    </div>
  )
}
