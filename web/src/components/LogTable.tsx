"use client";

import { Fragment, useEffect, useState } from "react";
import type { StructuredLog } from "@/lib/api";
import { LevelTag } from "./StatusBadge";

const PAGE_SIZE = 25;

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function LogTable({
  logs,
  onTraceClick,
}: {
  logs: StructuredLog[];
  onTraceClick?: (traceId: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  // Mot cum co the gom hang tram log (log_ids gop don khi merge cluster theo
  // thoi gian, xem clustering/src/storage.py) - dump het ra 1 bang se lam
  // trang dai hang chuc nghin px, khong dung duoc. Hien theo trang, tai them
  // theo yeu cau thay vi phan trang server (API khong ho tro offset).
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
        Không có log nào khớp.
      </div>
    );
  }

  const visibleLogs = logs.slice(0, visibleCount);
  const hasMore = visibleCount < logs.length;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
          <tr>
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Level</th>
            <th className="px-3 py-2 font-medium">Service</th>
            <th className="px-3 py-2 font-medium">Message</th>
            <th className="px-3 py-2 font-medium">Trace</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {visibleLogs.map((log) => {
            const rowKey = log.log_id ?? `${log.trace_id}-${log.timestamp}`;
            const isOpen = expanded === rowKey;
            const hasDetail = Boolean(log.stack_trace || (log.metadata && Object.keys(log.metadata).length > 0));
            return (
              <Fragment key={rowKey}>
                <tr
                  className={`${hasDetail ? "cursor-pointer" : ""} hover:bg-slate-50 dark:hover:bg-slate-900/60`}
                  onClick={() => hasDetail && setExpanded(isOpen ? null : rowKey)}
                >
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {formatTime(log.timestamp)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <LevelTag level={log.level} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-300">{log.service}</td>
                  <td className="px-3 py-2 text-slate-800 dark:text-slate-200">
                    {log.message}
                    {hasDetail && (
                      <span className="ml-2 text-xs text-slate-400">{isOpen ? "▲" : "▼ chi tiết"}</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onTraceClick?.(log.trace_id);
                      }}
                      className="font-mono text-xs text-indigo-600 underline decoration-dotted underline-offset-2 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
                      title="Xem toàn bộ log của trace này"
                    >
                      {log.trace_id.slice(0, 12)}
                    </button>
                  </td>
                </tr>
                {isOpen && hasDetail && (
                  <tr className="bg-slate-50 dark:bg-slate-900/40">
                    <td colSpan={5} className="px-3 py-3">
                      {log.stack_trace && (
                        <pre className="mb-2 max-h-48 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                          {log.stack_trace}
                        </pre>
                      )}
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
                          {Object.entries(log.metadata).map(([k, v]) => (
                            <div key={k} className="flex gap-1">
                              <dt className="font-medium text-slate-500 dark:text-slate-400">{k}:</dt>
                              <dd className="font-mono text-slate-700 dark:text-slate-300">{String(v)}</dd>
                            </div>
                          ))}
                        </dl>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {hasMore && (
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          <span>
            Đang hiện {visibleLogs.length}/{logs.length} log
          </span>
          <button
            type="button"
            onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
            className="rounded-md bg-white px-2.5 py-1 font-medium text-indigo-600 ring-1 ring-inset ring-slate-200 hover:bg-indigo-50 dark:bg-slate-800 dark:text-indigo-400 dark:ring-slate-700 dark:hover:bg-slate-700"
          >
            Xem thêm {Math.min(PAGE_SIZE, logs.length - visibleCount)}
          </button>
        </div>
      )}
    </div>
  );
}
