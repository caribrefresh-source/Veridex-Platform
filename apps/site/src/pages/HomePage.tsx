import { Link } from 'react-router-dom';
import { SiteFooter } from '../components/SiteFooter';
import { SiteHeader } from '../components/SiteHeader';
import { PageMeta } from '../components/PageMeta';

const features = [
  ['Document Intelligence', 'A focused path from document intake to structured, reviewable information.'],
  ['Security by Design', 'An architecture built around least privilege, encrypted transport, and auditable operations.'],
  ['Workflow Automation', 'A planned foundation for dependable, observable document workflows.'],
  ['Data Platform', 'Purpose-specific data services designed for documents, events, search, and workflow state.'],
  ['AI Services', 'A roadmap for retrieval, embeddings, and knowledge-assisted document analysis.'],
];

export function HomePage() {
  return (
    <div className="page-shell">
      <PageMeta title="Veridex | Document Intelligence" path="/" />
      <SiteHeader />
      <main>
        <section className="hero" aria-labelledby="home-heading">
          <p className="eyebrow">Document Intelligence Platform</p>
          <h1 id="home-heading">Turn complex documents into reliable workflows.</h1>
          <p className="hero-copy">
            Veridex is building a secure platform for turning document-heavy operations into observable,
            AI-assisted processes.
          </p>
          <Link className="button" to="/plans">Explore plans</Link>
        </section>
        <section className="features" aria-labelledby="capabilities-heading">
          <h2 id="capabilities-heading">Platform capabilities</h2>
          <div className="feature-grid">
            {features.map(([title, description]) => (
              <article className="card" key={title}>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
