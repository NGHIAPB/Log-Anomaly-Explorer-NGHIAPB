import { ClusterList } from "@/components/ClusterList";
import { LogSearch } from "@/components/LogSearch";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ trace_id?: string }>;
}) {
  const { trace_id } = await searchParams;

  return (
    <div className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6">
      <ClusterList />
      <LogSearch initialTraceId={trace_id} />
    </div>
  );
}
