import { createHash } from "node:crypto";

import type { Paper } from "../types";

export function normalizeText(value: string): string {
  return (value.toLowerCase().match(/[a-z0-9]+/g) ?? []).join(" ");
}

export function tokens(value: string): Set<string> {
  return new Set(normalizeText(value).split(" ").filter((token) => token.length > 1));
}

export function tokenCoverage(left: string, right: string): number {
  const leftTokens = tokens(left);
  const rightTokens = tokens(right);
  if (!leftTokens.size || !rightTokens.size) return 0;
  const overlap = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  return overlap / Math.min(leftTokens.size, rightTokens.size);
}

export function tokenJaccard(left: string, right: string): number {
  const leftTokens = tokens(left);
  const rightTokens = tokens(right);
  if (!leftTokens.size || !rightTokens.size) return 0;
  const overlap = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  return overlap / new Set([...leftTokens, ...rightTokens]).size;
}

export function authorOverlap(left: Paper, right: Paper): number {
  const surnames = (authors: string[]) =>
    new Set(authors.map((author) => normalizeText(author).split(" ").at(-1)).filter(Boolean));
  const leftNames = surnames(left.authors);
  const rightNames = surnames(right.authors);
  if (!leftNames.size || !rightNames.size) return 0;
  return [...leftNames].filter((name) => rightNames.has(name)).length /
    Math.min(leftNames.size, rightNames.size);
}

function normalizedIdentifier(source: string, value: string): string {
  let normalized = value.trim().toLowerCase();
  if (source === "arxiv") normalized = normalized.replace(/v\d+$/, "");
  if (source === "doi") normalized = normalized.replace(/^https:\/\/doi\.org\//, "");
  return normalized;
}

export function canonicalIdFor(papers: Paper[]): string {
  for (const source of ["doi", "arxiv", "openalex", "semantic_scholar"]) {
    const values = papers
      .map((paper) => paper.source_ids[source])
      .filter(Boolean)
      .map((value) => normalizedIdentifier(source, value))
      .sort();
    if (values.length) {
      return `paper:${createHash("sha256").update(`${source}:${values[0]}`).digest("hex").slice(0, 24)}`;
    }
  }
  const primary = [...papers].sort((a, b) => a.published_date.localeCompare(b.published_date))[0];
  const fallback = `${normalizeText(primary.title)}|${primary.published_date}|${[...tokens(primary.authors.join(" "))].sort().join("|")}`;
  return `paper:${createHash("sha256").update(fallback).digest("hex").slice(0, 24)}`;
}

function sharesIdentifier(left: Paper, right: Paper): boolean {
  return Object.entries(left.source_ids).some(([source, value]) => {
    const other = right.source_ids[source];
    return other && normalizedIdentifier(source, value) === normalizedIdentifier(source, other);
  });
}

function recordsMatch(left: Paper, right: Paper): boolean {
  if (sharesIdentifier(left, right)) return true;
  const dateDelta = Math.abs(
    (Date.parse(left.published_date) - Date.parse(right.published_date)) / 86_400_000,
  );
  return (
    tokenJaccard(left.title, right.title) >= 0.82 &&
    authorOverlap(left, right) >= 0.5 &&
    dateDelta <= 30
  );
}

function mergeGroup(group: Paper[]): Paper {
  const primary = [...group].sort(
    (left, right) =>
      right.abstract.length - left.abstract.length ||
      (right.citation_count ?? 0) - (left.citation_count ?? 0),
  )[0];
  const sourceIds: Record<string, string> = {};
  const sourceUrls: Record<string, string> = {};
  const authors: string[] = [];
  const seenAuthors = new Set<string>();
  for (const paper of group) {
    Object.assign(sourceIds, paper.source_ids);
    Object.assign(sourceUrls, paper.source_urls);
    for (const author of paper.authors) {
      if (!seenAuthors.has(author.toLowerCase())) {
        seenAuthors.add(author.toLowerCase());
        authors.push(author);
      }
    }
  }
  return {
    ...primary,
    canonical_id: canonicalIdFor(group),
    source_ids: sourceIds,
    source_urls: sourceUrls,
    authors,
    published_date: group.map((paper) => paper.published_date).sort()[0],
    citation_count: Math.max(...group.map((paper) => paper.citation_count ?? 0)) || null,
  };
}

export function reconcilePapers(papers: Paper[]): Paper[] {
  const groups: Paper[][] = [];
  for (const paper of papers) {
    const group = groups.find((candidate) => candidate.some((item) => recordsMatch(item, paper)));
    if (group) group.push(paper);
    else groups.push([paper]);
  }
  return groups.map(mergeGroup);
}
