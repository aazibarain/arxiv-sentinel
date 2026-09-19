import { NextRequest, NextResponse } from "next/server";

import { digest } from "@/lib/data";

export function GET(request: NextRequest) {
  const requestedDate = request.nextUrl.searchParams.get("date");
  const papers = !requestedDate || requestedDate === digest.digest_date ? digest.papers : [];
  return NextResponse.json({
    date: requestedDate ?? digest.digest_date,
    available_dates: [digest.digest_date],
    count: papers.length,
    papers,
  });
}
