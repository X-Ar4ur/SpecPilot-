import { PageHeader } from "../../../components/page-header";
import { RunDetail } from "../../../components/runs/run-detail";

export default function RunDetailPage({
  params,
}: {
  params: { run_id: string };
}) {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Run Detail"
        title={params.run_id}
        description="执行摘要、失败分类、报告链接和原始 JSON。"
      />
      <RunDetail runId={params.run_id} />
    </div>
  );
}
