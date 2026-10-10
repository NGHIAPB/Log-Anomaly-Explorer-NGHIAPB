"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, type SearchParams, type StructuredLog, searchLogs } from "@/lib/api";
import { LogTable } from "./LogTable";

export function LogSearch({ initialTraceId }: { initialTraceId?: string }) {
  const [form, setForm] = useState<SearchParams>({ trace_id: initialTraceId ?? "" });
  const [results, setResults] = useState<StructuredLog[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  const runSearch = (params: SearchParams) => {
    setLoading(true);
    setError(null);
    searchLogs(params)
      .then((res) => {
        setResults(res.results);
        setTotal(res.total);
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Tìm kiếm thất bại.");
        setResults(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (initialTraceId) {
      setForm({ trace_id: initialTraceId });
      runSearch({ trace_id: initialTraceId });
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [initialTraceId]);

  return (
    <section ref={sectionRef}>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Search log
      </h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(form);
        }}
        className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5"
      >
        <input
          type="text"
          placeholder="service (vd. demo-web)"
          value={form.service ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, service: e.target.value }))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
        <input
          type="text"
          placeholder="trace_id"
          value={form.trace_id ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, trace_id: e.target.value }))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900 placeholder:font-sans placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
        <input
          type="text"
          placeholder="từ khoá trong message"
          value={form.q ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, q: e.target.value }))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
        <input
          type="datetime-local"
          value={form.from ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, from: e.target.value }))}
          title="Từ thời điểm (mặc định 24h gần nhất)"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Đang tìm…" : "Tìm kiếm"}
        </button>
      </form>

      {error && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {results !== null && !error && (
        <>
          <p className="mb-2 text-xs text-slate-400">{total} kết quả</p>
          <LogTable logs={results} onTraceClick={(traceId) => runSearch({ trace_id: traceId })} />
        </>
      )}
    </section>
  );
}
