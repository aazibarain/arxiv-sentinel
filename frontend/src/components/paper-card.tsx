import Link from "next/link";
import { ArrowUpRight, BookOpen, Fingerprint, Users } from "lucide-react";

import { topicFor } from "@/lib/data";
import type { Paper } from "@/lib/types";

export function PaperCard({ paper, index }: { paper: Paper; index: number }) {
  return (
    <article className="paper-card">
      <div className="paper-card-top">
        <span className="paper-number">{String(index).padStart(2, "0")}</span>
        <div className="paper-badges">
          <span className="topic-badge">{topicFor(paper)}</span>
          <span className={`verdict-badge ${paper.novelty_verdict}`}>{paper.novelty_verdict}</span>
        </div>
      </div>
      <div className="paper-card-body">
        <p className="paper-date">PUBLISHED {paper.published_date}</p>
        <h3>{paper.title}</h3>
        <p className="authors"><Users size={15} /> {paper.authors.slice(0, 3).join(", ")}{paper.authors.length > 3 ? ` +${paper.authors.length - 3}` : ""}</p>
        <p className="summary">{paper.summary}</p>
        <div className="score-row">
          <div><span>Relevance</span><strong>{Math.round((paper.relevance_score ?? 0) * 100)}%</strong></div>
          <div><span>Novelty</span><strong>{Math.round((paper.novelty_score ?? 0) * 100)}%</strong></div>
          <div><span>Evidence</span><strong>{paper.summary_citations.length} spans</strong></div>
        </div>
      </div>
      <div className="paper-card-footer">
        <span><Fingerprint size={15} /> {Object.keys(paper.source_ids).join(" + ")}</span>
        <Link href={`/paper/${encodeURIComponent(paper.canonical_id)}`}>
          <BookOpen size={16} /> Inspect paper <ArrowUpRight size={15} />
        </Link>
      </div>
    </article>
  );
}
