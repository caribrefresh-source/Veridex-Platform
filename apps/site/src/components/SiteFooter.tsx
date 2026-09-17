import { Link } from 'react-router-dom';

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>Veridex · Intelligent document automation</span>
      <nav aria-label="Footer">
        <Link to="/">Home</Link>
        <Link to="/plans">Plans</Link>
      </nav>
    </footer>
  );
}
