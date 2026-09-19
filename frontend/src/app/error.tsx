"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="not-found">
      <span>ERROR</span>
      <h1>The signal dropped.</h1>
      <p>The dashboard hit an unexpected problem.</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}
