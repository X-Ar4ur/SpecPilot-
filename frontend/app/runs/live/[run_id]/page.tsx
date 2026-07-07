import { LiveRunConsole } from "../../../../components/live/live-run-console";

export default function LiveRunPage({
  params,
}: {
  params: { run_id: string };
}) {
  return <LiveRunConsole runId={params.run_id} />;
}
