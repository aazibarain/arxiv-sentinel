import { Dashboard } from "@/components/dashboard";
import { loadLatestDigest } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Home() {
  return <Dashboard result={await loadLatestDigest()} />;
}
