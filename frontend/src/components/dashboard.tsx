"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Database, Radar, Search, Sparkles } from "lucide-react";

import { PaperCard } from "@/components/paper-card";
import { topicFor } from "@/lib/data";
import type { Digest } from "@/lib/types";

export function Dashboard({ digest }: { digest: Digest }) {
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("All signals");
  const topics = ["All signals", ...new Set(digest.papers.map(topicFor))];
  const filtered = useMemo(() => {
    const normalizedQuery = query.toLowerCase().trim();
    return digest.papers.filter((paper) => {
      const matchesQuery =
        !normalizedQuery ||
        `${paper.title} ${paper.authors.join(" ")} ${paper.summary}`
          .toLowerCase()
          .includes(normalizedQuery);
      const matchesTopic = topic === "All signals" || topicFor(paper) === topic;
      return matchesQuery && matchesTopic;
    });
  }, [digest.papers, query, topic]);

  const meanRelevance = Math.round(
    (digest.papers.reduce((total, paper) => total + (paper.relevance_score ?? 0), 0) /
      digest.papers.length) *
      100,
  );

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
              <span><CalendarDays size={16} /> Digest · {digest.digest_date}</span>
              <span className="live-dot">System online</span>
            </div>
          </div>
          <div className="signal-panel" aria-label="Digest statistics">
            <div className="signal-orbit"><span>AI</span></div>
            <div className="signal-stat top"><strong>{digest.papers.length}</strong><span>papers surfaced</span></div>
            <div className="signal-stat right"><strong>{meanRelevance}%</strong><span>mean relevance</span></div>
            <div className="signal-stat bottom"><strong>3</strong><span>sources watched</span></div>
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
