import { NextResponse } from "next/server";

import { loadLatestDigest } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET() {
  const result = await loadLatestDigest();
  if (!result.digest) {
    return NextResponse.json(
      { state: result.state, detail: result.detail, count: 0, papers: [] },
      { status: result.state === "empty" ? 200 : 503 },
    );
  }
  return NextResponse.json({ ...result.digest, count: result.digest.papers.length });
}
