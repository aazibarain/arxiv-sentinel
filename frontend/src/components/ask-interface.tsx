"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { ArrowRight, Bot, CheckCircle2, CornerDownLeft, Quote, Sparkles } from "lucide-react";

import type { QAAnswer } from "@/lib/types";

const suggestions = [
  "How do attack and defense strategies differ across these papers?",
  "What do the papers reveal about the limits of safety training?",
  "Which findings suggest attacks transfer across models?",
];

export function AskInterface() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<QAAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (question.trim().length < 4 || loading) return;
    setLoading(true);
    setError("");
    setAnswer(null);
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "The corpus could not answer that question.");
      setAnswer(payload as QAAnswer);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="ask-page">
      <section className="ask-intro">
        <div className="eyebrow"><Sparkles size={15} /> GROUNDED CORPUS Q&A</div>
        <h1>Interrogate the research,<br /><em>not a black box.</em></h1>
        <p>
          Ask across the monitored corpus. Every factual answer is checked against exact passages
          in the retrieved abstracts before it reaches you.
        </p>
      </section>

      <section className="ask-workspace">
        <div className="ask-status">
          <span><Bot size={18} /> Sentinel analyst</span>
          <span className="verified"><CheckCircle2 size={15} /> Grounding gate active</span>
        </div>
        <form onSubmit={submit} className="ask-form">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a cross-paper question about attacks, defenses, transferability, or safety training…"
            aria-label="Research question"
            rows={4}
          />
          <div className="ask-form-footer">
            <span>Answers use retrieved abstracts only</span>
            <button type="submit" disabled={loading || question.trim().length < 4}>
              {loading ? "Analyzing corpus…" : "Ask Sentinel"} <CornerDownLeft size={17} />
            </button>
          </div>
        </form>

        {!answer && !loading && !error && (
          <div className="suggestions">
            <p>Try a research question</p>
            {suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => setQuestion(suggestion)}>
                {suggestion}<ArrowRight size={15} />
              </button>
            ))}
          </div>
        )}
        {loading && <div className="answer-loading"><span /><span /><span /> Retrieving and validating evidence</div>}
        {error && <div className="error-panel"><strong>Couldn’t complete the answer.</strong><p>{error}</p></div>}

        {answer && (
          <article className="answer-panel">
            <div className="answer-label">
              <span><Bot size={18} /> GROUNDED ANSWER</span>
              <span className={`answerability ${answer.answerability}`}>{answer.answerability}</span>
            </div>
            <p className="answer-copy">{answer.answer}</p>
            {answer.uncertainty && (
              <div className="answer-uncertainty">
                <strong>Evidence boundary</strong>
                <p>{answer.uncertainty}</p>
              </div>
            )}
            <div className="citation-list">
              <h2>{answer.citations.length ? "Evidence trail" : "No supportable citations"}</h2>
              {answer.citations.map((citation, index) => (
                <div className="citation-card" key={`${citation.canonical_id}-${index}`}>
                  <span className="citation-index">{index + 1}</span>
                  <div>
                    <Link href={`/paper/${encodeURIComponent(citation.canonical_id)}`}>{citation.title}</Link>
                    <blockquote><Quote size={14} /> {citation.source_span}</blockquote>
                    <p>{citation.claim}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>
        )}
      </section>
    </main>
  );
}
