import { XMLParser } from "fast-xml-parser";

import type { Paper } from "../types";

export const SOURCE_NAMES = ["arxiv", "semantic_scholar", "openalex"] as const;
type SourceName = (typeof SOURCE_NAMES)[number];

const DISCOVERY_QUERIES = [
  "adversarial machine learning",
  "AI security",
  "language model security",
  "machine learning privacy",
];

function emptyPaper(input: Pick<Paper, "title" | "abstract" | "authors" | "published_date" | "source_ids" | "source_urls"> & Partial<Paper>): Paper {
  return {
    canonical_id: "",
    citation_count: null,
    relevance_score: null,
    novelty_score: null,
    novelty_verdict: null,
    summary: null,
    why_it_matters: null,
    summary_confidence: null,
    uncertainty: null,
    summary_citations: [],
    ingested_at: new Date().toISOString(),
    ...input,
  };
}

async function fetchWithRetry(url: string, init: RequestInit = {}, attempts = 3): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    let retryDelayMs = 600 * 2 ** attempt;
    try {
      const response = await fetch(url, {
        ...init,
        headers: { "User-Agent": "ArxivSentinel/1.0", ...init.headers },
        signal: AbortSignal.timeout(20_000),
      });
      if (response.ok) return response;
      if (response.status !== 429 && response.status < 500) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      lastError = new Error(`${response.status} ${response.statusText}`);
      const retryAfterSeconds = Number(response.headers.get("retry-after"));
      if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
        retryDelayMs = Math.max(retryDelayMs, Math.min(retryAfterSeconds * 1000, 5_000));
      }
    } catch (error) {
      lastError = error;
    }
    if (attempt < attempts - 1) await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
  }
  throw lastError instanceof Error ? lastError : new Error("Source request failed");
}

function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

function xmlText(value: unknown): string {
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (value && typeof value === "object" && "#text" in value) {
    return String((value as { "#text": unknown })["#text"]).replace(/\s+/g, " ").trim();
  }
  return "";
}

export function parseArxivFeed(xml: string, startDate: string, endDate: string): Paper[] {
  const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "" });
  const parsed = parser.parse(xml) as { feed?: { entry?: unknown | unknown[] } };
  return asArray(parsed.feed?.entry)
    .map((raw) => raw as Record<string, unknown>)
    .filter((entry) => {
      const published = xmlText(entry.published).slice(0, 10);
      return published >= startDate && published < endDate;
    })
    .map((entry) => {
      const entryUrl = xmlText(entry.id);
      const arxivId = entryUrl.split("/").at(-1)?.replace(/v\d+$/, "") ?? "";
      const authors = asArray(entry.author as Record<string, unknown> | Record<string, unknown>[])
        .map((author) => xmlText(author.name))
        .filter(Boolean);
      return emptyPaper({
        title: xmlText(entry.title),
        abstract: xmlText(entry.summary),
        authors,
        published_date: xmlText(entry.published).slice(0, 10),
        source_ids: { arxiv: arxivId },
        source_urls: { arxiv: `https://arxiv.org/abs/${arxivId}` },
      });
    })
    .filter((paper) => paper.title && paper.abstract && paper.source_ids.arxiv);
}

export async function fetchArxiv(startDate: string, endDate: string, limit: number): Promise<Paper[]> {
  const categoryQuery = ["cs.CR", "cs.AI", "cs.LG", "stat.ML"].map((value) => `cat:${value}`).join(" OR ");
  const params = new URLSearchParams({
    search_query: categoryQuery,
    start: "0",
    max_results: String(Math.min(Math.max(limit * 5, 100), 500)),
    sortBy: "submittedDate",
    sortOrder: "descending",
  });
  const response = await fetchWithRetry(`https://export.arxiv.org/api/query?${params}`);
  return parseArxivFeed(await response.text(), startDate, endDate).slice(0, limit);
}

type SemanticScholarItem = {
  paperId?: string;
  externalIds?: Record<string, string>;
  url?: string;
  title?: string;
  abstract?: string;
  authors?: Array<{ name?: string }>;
  publicationDate?: string;
  citationCount?: number;
};

export function parseSemanticScholarItem(item: SemanticScholarItem): Paper | null {
  if (!item.paperId || !item.title || !item.abstract || !item.publicationDate) return null;
  const ids: Record<string, string> = { semantic_scholar: item.paperId };
  if (item.externalIds?.ArXiv) ids.arxiv = item.externalIds.ArXiv.replace(/v\d+$/, "");
  if (item.externalIds?.DOI) ids.doi = item.externalIds.DOI.toLowerCase();
  return emptyPaper({
    title: item.title,
    abstract: item.abstract,
    authors: (item.authors ?? []).flatMap((author) => (author.name ? [author.name] : [])),
    published_date: item.publicationDate,
    source_ids: ids,
    source_urls: { semantic_scholar: item.url ?? `https://www.semanticscholar.org/paper/${item.paperId}` },
    citation_count: item.citationCount ?? null,
  });
}

export async function fetchSemanticScholar(startDate: string, endDate: string, limit: number): Promise<Paper[]> {
  const rotationSeed = Number(endDate.replaceAll("-", ""));
  const queries = [DISCOVERY_QUERIES[rotationSeed % DISCOVERY_QUERIES.length]];
  const perQuery = Math.min(100, Math.max(1, limit));
  const records = new Map<string, Paper>();
  const failures: Error[] = [];
  const inclusiveEnd = new Date(`${endDate}T00:00:00Z`);
  inclusiveEnd.setUTCDate(inclusiveEnd.getUTCDate() - 1);
  for (const query of queries) {
    const params = new URLSearchParams({
      query,
      publicationDateOrYear: `${startDate}:${inclusiveEnd.toISOString().slice(0, 10)}`,
      fields: "paperId,externalIds,url,title,abstract,authors,publicationDate,citationCount",
      limit: String(perQuery),
    });
    try {
      const response = await fetchWithRetry(`https://api.semanticscholar.org/graph/v1/paper/search?${params}`);
      const payload = (await response.json()) as { data?: SemanticScholarItem[] };
      for (const item of payload.data ?? []) {
        const paper = parseSemanticScholarItem(item);
        if (paper) records.set(paper.source_ids.semantic_scholar, paper);
      }
    } catch (error) {
      failures.push(error instanceof Error ? error : new Error("Semantic Scholar query failed"));
    }
  }
  if (!records.size && failures.length) throw failures.at(-1);
  if (failures.length) console.warn(`[ingest:semantic_scholar] ${failures.length} discovery queries failed; preserving partial results`);
  return [...records.values()].slice(0, limit);
}

type OpenAlexItem = {
  id?: string;
  title?: string;
  publication_date?: string;
  abstract_inverted_index?: Record<string, number[]>;
  ids?: Record<string, string>;
  primary_location?: { landing_page_url?: string };
  authorships?: Array<{ author?: { display_name?: string } }>;
  cited_by_count?: number;
};

export function reconstructOpenAlexAbstract(index?: Record<string, number[]>): string | null {
  if (!index) return null;
  const positioned = Object.entries(index).flatMap(([token, positions]) =>
    positions.filter((position) => Number.isInteger(position) && position >= 0).map((position) => [position, token] as const),
  );
  if (!positioned.length) return null;
  return positioned.sort((left, right) => left[0] - right[0]).map(([, token]) => token).join(" ");
}

export function parseOpenAlexItem(item: OpenAlexItem): Paper | null {
  const abstract = reconstructOpenAlexAbstract(item.abstract_inverted_index);
  if (!item.id || !item.title || !item.publication_date || !abstract) return null;
  const openAlexId = item.id.split("/").at(-1) ?? item.id;
  const ids: Record<string, string> = { openalex: openAlexId };
  if (item.ids?.arxiv) ids.arxiv = item.ids.arxiv.split("/").at(-1)?.replace(/v\d+$/, "") ?? item.ids.arxiv;
  if (item.ids?.doi) ids.doi = item.ids.doi.replace(/^https:\/\/doi\.org\//, "").toLowerCase();
  return emptyPaper({
    title: item.title,
    abstract,
    authors: (item.authorships ?? []).flatMap((entry) => entry.author?.display_name ? [entry.author.display_name] : []),
    published_date: item.publication_date,
    source_ids: ids,
    source_urls: { openalex: item.primary_location?.landing_page_url ?? item.id },
    citation_count: item.cited_by_count ?? null,
  });
}

export async function fetchOpenAlex(startDate: string, endDate: string, limit: number): Promise<Paper[]> {
  const perQuery = Math.min(200, Math.max(1, Math.ceil(limit / DISCOVERY_QUERIES.length)));
  const records = new Map<string, Paper>();
  const inclusiveEnd = new Date(`${endDate}T00:00:00Z`);
  inclusiveEnd.setUTCDate(inclusiveEnd.getUTCDate() - 1);
  for (const query of DISCOVERY_QUERIES) {
    const params = new URLSearchParams({
      search: query,
      filter: `from_publication_date:${startDate},to_publication_date:${inclusiveEnd.toISOString().slice(0, 10)}`,
      "per-page": String(perQuery),
      sort: "publication_date:desc",
    });
    if (process.env.OPENALEX_MAILTO) params.set("mailto", process.env.OPENALEX_MAILTO);
    const response = await fetchWithRetry(`https://api.openalex.org/works?${params}`);
    const payload = (await response.json()) as { results?: OpenAlexItem[] };
    for (const item of payload.results ?? []) {
      const paper = parseOpenAlexItem(item);
      if (paper) records.set(paper.source_ids.openalex, paper);
    }
  }
  return [...records.values()].slice(0, limit);
}

export async function fetchAllSources(startDate: string, endDate: string, limit: number): Promise<{
  papers: Paper[];
  sourceCounts: Record<string, number>;
  sourceErrors: Record<string, string>;
}> {
  const sources: Array<[SourceName, () => Promise<Paper[]>]> = [
    ["arxiv", () => fetchArxiv(startDate, endDate, limit)],
    ["semantic_scholar", () => fetchSemanticScholar(startDate, endDate, limit)],
    ["openalex", () => fetchOpenAlex(startDate, endDate, limit)],
  ];
  const results = await Promise.allSettled(sources.map(([, fetchSource]) => fetchSource()));
  const papers: Paper[] = [];
  const sourceCounts: Record<string, number> = {};
  const sourceErrors: Record<string, string> = {};
  results.forEach((result, index) => {
    const name = sources[index][0];
    if (result.status === "fulfilled") {
      sourceCounts[name] = result.value.length;
      papers.push(...result.value);
    } else {
      sourceCounts[name] = 0;
      sourceErrors[name] = result.reason instanceof Error ? result.reason.message : "Unknown source failure";
    }
  });
  return { papers, sourceCounts, sourceErrors };
}
