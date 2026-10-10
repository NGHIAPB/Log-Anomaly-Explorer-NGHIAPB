"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { ApiError, type ClusterRecord, getCluster } from "@/lib/api";
import { ClusterStatusBadge } from "@/components/StatusBadge";
import { LogTable } from "@/components/LogTable";

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export default function ClusterDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const [cluster, setCluster] = useState<ClusterRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAllTraces, setShowAllTraces] = useState(false);

  const TRACE_PREVIEW_COUNT = 40;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCluster(id)
      .then((res) => !cancelled && setCluster(res))
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError(`Không tìm thấy cụm "${id}".`);
        } else {
          setError(err instanceof ApiError ? err.message : "Không tải được chi tiết cụm.");
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <Link href="/" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
        ← Về danh sách cụm
      </Link>

      {loading && (
        <div className="rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-400 dark:border-slate-800">
          Đang tải…
        </div>
      )}

      {error && !loading && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {cluster && !loading && !error && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <ClusterStatusBadge status={cluster.status} />
              <span className="font-mono text-xs text-slate-400">{cluster.cluster_id}</span>
            </div>
            <h1 className="mb-4 break-words font-mono text-lg font-semibold text-slate-900 dark:text-white">
              {cluster.signature || "(không có signature)"}
            </h1>
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Anomaly score</dt>
                <dd className="mt-1 font-mono text-xl font-semibold text-slate-900 dark:text-white">
                  {cluster.score.toFixed(2)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Logs liên quan</dt>
                <dd className="mt-1 text-xl font-semibold text-slate-900 dark:text-white">
                  {cluster.logs?.length ?? cluster.log_ids?.length ?? 0}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">First seen</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{formatTime(cluster.first_seen)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Last seen</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{formatTime(cluster.last_seen)}</dd>
              </div>
            </dl>

            {cluster.trace_ids?.length > 0 && (
              <div className="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800">
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">
                  Trace / request liên quan ({cluster.trace_ids.length})
                </p>
                <div className="flex flex-wrap gap-2">
                  {(showAllTraces ? cluster.trace_ids : cluster.trace_ids.slice(0, TRACE_PREVIEW_COUNT)).map(
                    (tid) => (
                      <button
                        key={tid}
                        onClick={() => router.push(`/?trace_id=${encodeURIComponent(tid)}`)}
                        className="rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600 hover:bg-indigo-100 hover:text-indigo-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-indigo-900/40 dark:hover:text-indigo-300"
                        title="Xem toàn bộ log của trace này"
                      >
                        {tid.slice(0, 16)}
                      </button>
                    ),
                  )}
                  {!showAllTraces && cluster.trace_ids.length > TRACE_PREVIEW_COUNT && (
                    <button
                      onClick={() => setShowAllTraces(true)}
                      className="rounded-md px-2 py-1 font-mono text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      +{cluster.trace_ids.length - TRACE_PREVIEW_COUNT} trace khác
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Log trong cụm
            </h2>
            <LogTable
              logs={cluster.logs ?? []}
              onTraceClick={(traceId) => router.push(`/?trace_id=${encodeURIComponent(traceId)}`)}
            />
          </section>
        </>
      )}
    </div>
  );
}
