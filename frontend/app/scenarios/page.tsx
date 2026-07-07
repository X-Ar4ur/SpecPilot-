import { PageHeader } from "../../components/page-header";
import { ScenarioTable } from "../../components/scenarios/scenario-table";

export default function ScenariosPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Scenario Console"
        title="测试场景"
        description="查看零 locator 场景、审核状态、步骤、预期结果与证据 JSON。"
      />
      <ScenarioTable />
    </div>
  );
}
