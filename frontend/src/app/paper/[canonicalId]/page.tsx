import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, CalendarDays, CheckCircle2, Fingerprint, Quote, Users } from "lucide-react";

import { getPaper, preferredSourceUrl, topicFor } from "@/lib/data";

export default async function PaperPage({ params }: PageProps<"/paper/[canonicalId]">) {
  const { canonicalId } = await params;
  const paper = getPaper(decodeURIComponent(canonicalId));
  if (!paper) notFound();
  const sourceUrl = preferredSourceUrl(paper);

  return (
    <main className="detail-page">
      <Link href="/" className="back-link"><ArrowLeft size={16} /> Back to daily digest</Link>
      <article className="detail-article">
        <header className="detail-header">
          <div className="paper-badges">
            <span className="topic-badge">{topicFor(paper)}</span>
            <span className={`verdict-badge ${paper.novelty_verdict}`}>{paper.novelty_verdict}</span>
          </div>
          <h1>{paper.title}</h1>
          <div className="detail-meta">
            <span><Users size={16} /> {paper.authors.slice(0, 5).join(", ")}{paper.authors.length > 5 ? ` +${paper.authors.length - 5}` : ""}</span>
            <span><CalendarDays size={16} /> {paper.published_date}</span>
            <span><Fingerprint size={16} /> {paper.canonical_id}</span>
          </div>
          {sourceUrl && <a className="source-button" href={sourceUrl} target="_blank" rel="noreferrer">Open source paper <ArrowUpRight size={16} /></a>}
        </header>

        <div className="detail-layout">
          <div className="detail-main">
            <section className="content-section">
              <span className="section-index">01 / SENTINEL SUMMARY</span>
              <h2>What the paper says</h2>
              <p className="lead-summary">{paper.summary}</p>
            </section>
            <section className="content-section why-section">
              <span className="section-index">02 / JUDGMENT</span>
              <h2>Why it matters</h2>
              <p>{paper.why_it_matters}</p>
            </section>
            <section className="content-section">
              <span className="section-index">03 / SOURCE ABSTRACT</span>
              <h2>Original evidence</h2>
              <p className="abstract-copy">{paper.abstract}</p>
            </section>
          </div>

          <aside className="evidence-rail">
            <div className="score-card">
              <span>Decision trace</span>
              <div><strong>{Math.round((paper.relevance_score ?? 0) * 100)}%</strong><small>semantic relevance</small></div>
              <div><strong>{Math.round((paper.novelty_score ?? 0) * 100)}%</strong><small>novelty score</small></div>
            </div>
            <div className="evidence-card">
              <h2><CheckCircle2 size={17} /> Grounding passed</h2>
              <p>Every generated claim below maps to an abstract span.</p>
              {paper.summary_citations.map((citation, index) => (
                <div className="evidence-item" key={citation.claim}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <p>{citation.claim}</p>
                  <blockquote><Quote size={13} /> {citation.source_span}</blockquote>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </article>
    </main>
  );
}
