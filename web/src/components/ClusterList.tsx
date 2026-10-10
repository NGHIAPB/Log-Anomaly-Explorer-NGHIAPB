"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, type ClusterRecord, type ClusterStatus, listClusters } from "@/lib/api";
import { ClusterStatusBadge } from "./StatusBadge";

const STATUS_FILTERS: { value: ClusterStatus | ""; label: string }[] = [
  { value: "", label: "Tất cả" },
  { value: "alerted", label: "Alerted" },
  { value: "anomalous", label: "Anomalous" },
  { value: "normal", label: "Normal" },
];

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function ScoreBar({ score }: { score: number }) {
  // Hien thi truc quan z-score so voi ANOMALY_THRESHOLD mac dinh (2.0, xem
  // clustering/README.md) - khong phai gia tri tuyet doi co tran, chi la
  // thanh do tuong doi de so sanh nhanh giua cac cum.
  const pct = Math.max(4, Math.min(100, (score / 6) * 100));
  const color = score >= 2 ? "bg-red-500" : score > 0 ? "bg-amber-400" : "bg-slate-300 dark:bg-slate-600";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-slate-600 dark:text-slate-300">{score.toFixed(2)}</span>
    </div>
  );
}

export function ClusterList() {
  const [status, setStatus] = useState<ClusterStatus | "">("");
  const [clusters, setClusters] = useState<ClusterRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listClusters({ status })
      .then((res) => {
        if (cancelled) return;
        const sorted = [...res.clusters].sort((a, b) => b.score - a.score);
        setClusters(sorted);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Không tải được danh sách cụm.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [status]);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Cụm bất thường
        </h2>
        <div className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-900">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              onClick={() => setStatus(f.value)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                status === f.value
                  ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {!error && loading && (
        <div className="rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-400 dark:border-slate-800">
          Đang tải…
        </div>
      )}

      {!error && !loading && clusters && clusters.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Không có cụm nào{status ? ` ở trạng thái "${status}"` : ""}.
        </div>
      )}

      {!error && clusters && clusters.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {clusters.map((c) => (
            <li key={c.cluster_id}>
              <Link
                href={`/clusters/${encodeURIComponent(c.cluster_id)}`}
                className="block h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-700"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <ClusterStatusBadge status={c.status} />
                  <span className="text-xs text-slate-400">{(c.trace_ids ?? []).length} trace</span>
                </div>
                <p className="mb-3 line-clamp-2 font-mono text-xs text-slate-600 dark:text-slate-300">
                  {c.signature || c.cluster_id}
                </p>
                <ScoreBar score={c.score} />
                <p className="mt-3 text-xs text-slate-400">Gần nhất: {formatTime(c.last_seen)}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
