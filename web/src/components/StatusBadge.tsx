import type { ClusterStatus, LogLevel } from "@/lib/api";

const CLUSTER_STYLES: Record<ClusterStatus, string> = {
  normal: "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700",
  anomalous:
    "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-800",
  alerted: "bg-red-100 text-red-700 ring-red-200 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-800",
};

const CLUSTER_LABELS: Record<ClusterStatus, string> = {
  normal: "Normal",
  anomalous: "Anomalous",
  alerted: "Alerted",
};

export function ClusterStatusBadge({ status }: { status: ClusterStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${CLUSTER_STYLES[status]}`}
    >
      {status === "alerted" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />}
      {CLUSTER_LABELS[status]}
    </span>
  );
}

const LEVEL_STYLES: Record<LogLevel, string> = {
  DEBUG: "text-slate-400",
  INFO: "text-sky-600 dark:text-sky-400",
  WARN: "text-amber-600 dark:text-amber-400",
  ERROR: "text-red-600 dark:text-red-400",
  FATAL: "text-red-700 dark:text-red-300 font-semibold",
};

export function LevelTag({ level }: { level: LogLevel }) {
  return <span className={`font-mono text-xs font-medium ${LEVEL_STYLES[level]}`}>{level}</span>;
}
