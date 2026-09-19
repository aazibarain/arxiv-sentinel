import Link from "next/link";

export default function NotFound() {
  return <main className="not-found"><span>404</span><h1>Signal not found.</h1><p>This paper is not in the monitored corpus.</p><Link href="/">Return to digest</Link></main>;
}
