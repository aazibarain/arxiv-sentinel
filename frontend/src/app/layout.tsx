import type { Metadata } from "next";
import Link from "next/link";
import { Binoculars, Code2, MessageSquareText } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArXiv Sentinel — AI Security Research Monitor",
  description: "Explainable AI-security paper monitoring with grounded summaries and corpus Q&A.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" data-scroll-behavior="smooth">
      <body className="min-h-full bg-[var(--canvas)] text-[var(--ink)]">
        <header className="site-header">
          <div className="site-header-inner">
            <Link href="/" className="brand" aria-label="ArXiv Sentinel home">
              <span className="brand-mark"><Binoculars size={19} strokeWidth={2.2} /></span>
              <span>
                <strong>ARXIV SENTINEL</strong>
                <small>AI SECURITY INTELLIGENCE</small>
              </span>
            </Link>
            <nav className="nav-links" aria-label="Primary navigation">
              <Link href="/">Daily digest</Link>
              <Link href="/ask"><MessageSquareText size={15} /> Ask corpus</Link>
              <a href="https://github.com/aazibarain/arxiv-sentinel" target="_blank" rel="noreferrer">
                <Code2 size={15} /> Repository
              </a>
            </nav>
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <span>ArXiv Sentinel</span>
          <span>Judgment you can inspect · Evidence you can trace</span>
        </footer>
      </body>
    </html>
  );
}
