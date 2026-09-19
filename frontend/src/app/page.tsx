import { Dashboard } from "@/components/dashboard";
import { digest } from "@/lib/data";

export default function Home() {
  return <Dashboard digest={digest} />;
}
