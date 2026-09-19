"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Database, Radar, Search, Sparkles } from "lucide-react";

import { PaperCard } from "@/components/paper-card";
import { topicFor } from "@/lib/papers";
import type { DigestLoadResult, Paper } from "@/lib/types";

const EMPTY_PAPERS: Paper[] = [];

export function Dashboard({ result }: { result: DigestLoadResult }) {
  const digest = result.digest;
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("All signals");
  const papers = digest?.papers ?? EMPTY_PAPERS;
  const topics = ["All signals", ...new Set(papers.map(topicFor))];
  const filtered = useMemo(() => {
    const normalizedQuery = query.toLowerCase().trim();
    return papers.filter((paper) => {
      const matchesQuery =
        !normalizedQuery ||
        `${paper.title} ${paper.authors.join(" ")} ${paper.summary}`
          .toLowerCase()
          .includes(normalizedQuery);
      const matchesTopic = topic === "All signals" || topicFor(paper) === topic;
      return matchesQuery && matchesTopic;
    });
  }, [papers, query, topic]);

  const meanRelevance = papers.length
    ? Math.round((papers.reduce((total, paper) => total + (paper.relevance_score ?? 0), 0) / papers.length) * 100)
    : 0;
  const reportingSources = digest
    ? Object.values(digest.source_counts).filter((count) => count > 0).length
    : 0;
  const statusLabel = result.state === "ready"
    ? "Live pipeline online"
    : result.state === "unconfigured"
      ? "Storage setup required"
      : result.state === "error"
        ? "Data store unavailable"
        : "Awaiting first ingestion";

  return (
    <main>
      <section className="hero-shell">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="eyebrow"><Radar size={15} /> DAILY RESEARCH SIGNAL</div>
            <h1>The papers that change the <em>security conversation.</em></h1>
            <p>
              Autonomous monitoring across arXiv, Semantic Scholar, and OpenAlex—filtered for
              relevance, tested for novelty, and summarized with traceable evidence.
            </p>
            <div className="hero-meta">
              <span><CalendarDays size={16} /> Digest · {digest?.digest_date ?? "pending"}</span>
              <span className={result.state === "ready" ? "live-dot" : "status-dot"}>{statusLabel}</span>
            </div>
          </div>
          <div className="signal-panel" aria-label="Digest statistics">
            <div className="signal-orbit"><span>AI</span></div>
            <div className="signal-stat top"><strong>{papers.length}</strong><span>papers surfaced</span></div>
            <div className="signal-stat right"><strong>{meanRelevance}%</strong><span>mean relevance</span></div>
            <div className="signal-stat bottom"><strong>{reportingSources}/3</strong><span>sources reporting</span></div>
          </div>
        </div>
      </section>

      <section className="dashboard-shell">
        <div className="section-heading">
          <div>
            <span className="section-index">01 / DAILY DIGEST</span>
            <h2>High-signal research</h2>
          </div>
          <p>Each decision exposes its relevance, novelty, source identity, and grounding trail.</p>
        </div>

        {!digest && (
          <div className={`system-state ${result.state}`}>
            <strong>{statusLabel}</strong>
            <p>{result.detail ?? "No digest is available yet."}</p>
          </div>
        )}

        {digest && <div className="pipeline-meta" aria-label="Pipeline status">
          <span>Generated {digest.generated_at.replace("T", " ").slice(0, 16)} UTC</span>
          <span>{digest.candidate_count} candidates</span>
          <span>{digest.relevant_count} relevant</span>
          <span>{digest.deduplicated_count} duplicate records merged</span>
          <span>{digest.relevance_method === "gemini_embedding" ? "Gemini semantic ranking" : "Lexical fallback ranking"}</span>
        </div>}

        {digest && Object.keys(digest.source_errors).length > 0 && (
          <div className="source-warning">
            <strong>Partial source coverage</strong>
            <p>{Object.entries(digest.source_errors).map(([source, error]) => `${source}: ${error}`).join(" · ")}</p>
          </div>
        )}

        <div className="toolbar">
          <label className="search-box">
            <Search size={18} />
            <span className="sr-only">Search papers</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search title, author, or finding…"
            />
          </label>
          <div className="topic-filter" role="group" aria-label="Filter by topic">
            {topics.map((item) => (
              <button
                type="button"
                key={item}
                onClick={() => setTopic(item)}
                className={topic === item ? "active" : ""}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="results-line">
          <span><Database size={15} /> {filtered.length} canonical papers</span>
          <span><Sparkles size={15} /> Gemini-grounded summaries</span>
        </div>

        <div className="paper-grid">
          {filtered.map((paper, index) => (
            <PaperCard key={paper.canonical_id} paper={paper} index={index + 1} />
          ))}
        </div>
        {!filtered.length && <div className="empty-state">No papers match those filters.</div>}
      </section>
    </main>
  );
}
