import { NavLink } from 'react-router-dom';

export function SiteHeader() {
  return (
    <header className="site-header">
      <nav className="nav" aria-label="Primary">
        <NavLink className="brand" to="/" aria-label="Veridex home">
          <img className="brand-logo" src="/veridex-logo.png" alt="Veridex AI" />
        </NavLink>
        <div className="nav-links">
          <NavLink to="/">Home</NavLink>
          <NavLink to="/plans">Plans</NavLink>
        </div>
      </nav>
    </header>
  );
}


