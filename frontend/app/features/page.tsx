import { FeatureTree } from "../../components/features/feature-tree";
import { PageHeader } from "../../components/page-header";

export default function FeaturesPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Feature Map"
        title="功能点树"
        description="按手册模块查看功能点、证据来源、覆盖状态和置信度。"
      />
      <FeatureTree />
    </div>
  );
}
