import { NavLink } from 'react-router-dom';

export function SiteHeader() {
  return (
    <header className="site-header">
      <nav className="nav" aria-label="Primary">
        <NavLink className="brand" to="/" aria-label="Veridex home">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>Veridex</span>
        </NavLink>
        <div className="nav-links">
          <NavLink to="/">Home</NavLink>
          <NavLink to="/plans">Plans</NavLink>
        </div>
      </nav>
    </header>
  );
}
