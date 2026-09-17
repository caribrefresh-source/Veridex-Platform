import { Link } from 'react-router-dom';
import { SiteFooter } from '../components/SiteFooter';
import { SiteHeader } from '../components/SiteHeader';
import { PageMeta } from '../components/PageMeta';

const included = [
  'Deployment planning around document volume and infrastructure capacity',
  'Security and isolation requirements assessed during solution design',
  'Workflow and human-review requirements mapped before implementation',
  'Auditability and compliance needs included in the delivery scope',
  'Direct engineering collaboration for onboarding and integration',
];

export function PlansPage() {
  return (
    <div className="page-shell">
      <PageMeta title="Plans | Veridex" path="/plans" />
      <SiteHeader />
      <main className="plans" aria-labelledby="plans-heading">
        <p className="eyebrow">Plans</p>
        <h1 id="plans-heading">Built around your organization.</h1>
        <p className="plans-copy">
          Veridex is deployed and licensed per organization. Each deployment is sized against document volume,
          compliance requirements, availability targets, and infrastructure footprint.
        </p>
        <section className="plan-card" aria-labelledby="included-heading">
          <h2 id="included-heading">What’s included</h2>
          <ul>
            {included.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
        <Link className="text-link" to="/">← Back to home</Link>
      </main>
      <SiteFooter />
    </div>
  );
}
