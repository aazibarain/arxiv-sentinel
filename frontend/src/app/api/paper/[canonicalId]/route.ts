import { NextResponse } from "next/server";

import { getPaper } from "@/lib/data";

export async function GET(
  _request: Request,
  context: RouteContext<"/api/paper/[canonicalId]">,
) {
  const { canonicalId } = await context.params;
  const paper = getPaper(decodeURIComponent(canonicalId));
  if (!paper) return NextResponse.json({ detail: "Paper not found" }, { status: 404 });
  return NextResponse.json(paper);
}
