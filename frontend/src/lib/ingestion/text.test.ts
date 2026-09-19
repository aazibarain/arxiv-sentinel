import { describe, expect, it } from "vitest";

import { paper } from "../test-fixtures";
import { canonicalIdFor, reconcilePapers } from "./text";

describe("paper reconciliation", () => {
  it("merges cross-source records sharing an arXiv id", () => {
    const arxiv = paper();
    const semanticScholar = paper({
      canonical_id: "paper:s2",
      source_ids: { arxiv: "2609.12345v2", semantic_scholar: "s2-id" },
      source_urls: { semantic_scholar: "https://www.semanticscholar.org/paper/s2-id" },
      citation_count: 8,
    });

    const reconciled = reconcilePapers([arxiv, semanticScholar]);

    expect(reconciled).toHaveLength(1);
    expect(reconciled[0].source_ids).toMatchObject({ arxiv: "2609.12345v2", semantic_scholar: "s2-id" });
    expect(reconciled[0].citation_count).toBe(8);
  });

  it("produces a stable canonical id independent of source order", () => {
    const first = paper();
    const second = paper({ source_ids: { semantic_scholar: "s2-id", doi: "10.1/example" } });
    expect(canonicalIdFor([first, second])).toBe(canonicalIdFor([second, first]));
  });
});
