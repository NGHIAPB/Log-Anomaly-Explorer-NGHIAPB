import Link from "next/link";

export function Header() {
  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            LA
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Log Anomaly Explorer</p>
            <p className="text-xs text-slate-400">Search · Clustering · Incident View</p>
          </div>
        </Link>
        <nav className="text-xs text-slate-400">AI-06 · SE2026-T04</nav>
      </div>
    </header>
  );
}
