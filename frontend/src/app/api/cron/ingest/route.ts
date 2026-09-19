import { NextResponse } from "next/server";

import { runProductionIngestion } from "@/lib/ingestion/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret) {
    console.error("[cron:ingest] CRON_SECRET is not configured");
    return NextResponse.json({ detail: "Scheduled ingestion is not configured." }, { status: 503 });
  }
  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  try {
    const digest = await runProductionIngestion();
    return NextResponse.json({
      ok: true,
      digest_date: digest.digest_date,
      paper_count: digest.papers.length,
      source_counts: digest.source_counts,
      source_errors: digest.source_errors,
      relevance_method: digest.relevance_method,
    });
  } catch (error) {
    console.error("[cron:ingest] failed", error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Ingestion failed." },
      { status: 500 },
    );
  }
}
