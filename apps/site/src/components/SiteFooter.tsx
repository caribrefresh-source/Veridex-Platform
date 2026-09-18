import { Link } from 'react-router-dom';

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-brand"><img src="/veridex-logo.png" alt="Veridex AI" /><span>Governed Document Intelligence</span></div>
      <nav aria-label="Footer">
        <Link to="/">Home</Link>
        <Link to="/plans">Plans</Link>
      </nav>
    </footer>
  );
}

