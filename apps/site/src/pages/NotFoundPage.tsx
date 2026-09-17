import { Link } from 'react-router-dom';
import { SiteHeader } from '../components/SiteHeader';
import { PageMeta } from '../components/PageMeta';

export function NotFoundPage() {
  return (
    <div className="page-shell">
      <PageMeta title="Page not found | Veridex" path="/404" />
      <SiteHeader />
      <main className="not-found">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p>The requested page is not part of this site.</p>
        <Link className="button" to="/">Return home</Link>
      </main>
    </div>
  );
}
