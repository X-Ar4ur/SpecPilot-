import { PageHeader } from "../../components/page-header";
import { RunHistory } from "../../components/runs/run-history";

export default function RunsPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Run History"
        title="执行记录"
        description="查看历史运行、失败分类、报告编号和 artifact 入口。"
      />
      <RunHistory />
    </div>
  );
}
