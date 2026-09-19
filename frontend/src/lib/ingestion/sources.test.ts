import { describe, expect, it } from "vitest";

import {
  parseArxivFeed,
  parseOpenAlexItem,
  parseSemanticScholarItem,
  reconstructOpenAlexAbstract,
} from "./sources";

describe("source adapters", () => {
  it("reconstructs an OpenAlex inverted abstract in position order", () => {
    expect(reconstructOpenAlexAbstract({ agents: [2], Secure: [0], AI: [1] })).toBe("Secure AI agents");
  });

  it("normalizes OpenAlex identifiers", () => {
    const result = parseOpenAlexItem({
      id: "https://openalex.org/W123",
      title: "Secure agents",
      publication_date: "2026-09-18",
      abstract_inverted_index: { Secure: [0], agents: [1], resist: [2], attacks: [3], today: [4] },
      ids: { arxiv: "https://arxiv.org/abs/2609.12345v2", doi: "https://doi.org/10.1/EXAMPLE" },
    });
    expect(result?.source_ids).toMatchObject({ openalex: "W123", arxiv: "2609.12345", doi: "10.1/example" });
  });

  it("rejects incomplete Semantic Scholar records", () => {
    expect(parseSemanticScholarItem({ paperId: "x", title: "No abstract" })).toBeNull();
  });

  it("parses an arXiv feed and honors the date window", () => {
    const xml = `<?xml version="1.0"?><feed><entry><id>http://arxiv.org/abs/2609.12345v2</id><title>Secure agents</title><summary>A complete abstract about secure artificial intelligence agents and attacks.</summary><published>2026-09-18T12:00:00Z</published><author><name>Ada Researcher</name></author></entry></feed>`;
    const result = parseArxivFeed(xml, "2026-09-18", "2026-09-19");
    expect(result).toHaveLength(1);
    expect(result[0].source_ids.arxiv).toBe("2609.12345");
  });
});
