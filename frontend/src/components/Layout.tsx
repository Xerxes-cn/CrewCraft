import { Link, Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <h1>
          <Link to="/" style={{ textDecoration: 'none', color: '#1a1a2e' }}>
            CrewCraft
          </Link>
        </h1>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
