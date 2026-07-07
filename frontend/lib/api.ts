import type {
  ArtifactList,
  CreateRunResponse,
  DoctorResponse,
  FixtureBindRequest,
  FixtureInventory,
  Job,
  Feature,
  ListResponse,
  ManualPipelineStartPayload,
  PipelineStartResponse,
  Run,
  RuntimeSettings,
  RuntimeSettingsPatch,
  ScenarioBindingStatus,
  ScenarioFixtureBinding,
  ScenarioSummary,
  TestScenario,
  TraceList,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, statusText: string, body: unknown) {
    super(`${status} ${statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(
  path: string,
  init: RequestInit & { body?: BodyInit | null } = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(response.status, response.statusText, body);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async listFeatures() {
    return fetchJson<ListResponse<Feature>>("/api/features");
  },
  async listScenarios(filters: Record<string, string | boolean | undefined> = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        params.set(key, String(value));
      }
    });
    const query = params.toString();
    return fetchJson<ListResponse<ScenarioSummary>>(
      `/api/scenarios${query ? `?${query}` : ""}`,
    );
  },
  async getScenario(scenarioId: string) {
    return fetchJson<TestScenario>(`/api/scenarios/${scenarioId}`);
  },
  async getScenarioBinding(scenarioId: string) {
    return fetchJson<ScenarioBindingStatus>(
      `/api/scenarios/${scenarioId}/binding`,
    );
  },
  async getFixtureInventory() {
    return fetchJson<FixtureInventory>("/api/fixtures/inventory");
  },
  async bindFixture(request: FixtureBindRequest) {
    return fetchJson<ScenarioFixtureBinding>("/api/fixtures/bind", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  async createRun(scenarioIds: string[]) {
    return fetchJson<CreateRunResponse>("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        scenario_ids: scenarioIds,
        mode: scenarioIds.length === 1 ? "single" : "suite",
        config: {},
      }),
    });
  },
  async listRuns() {
    return fetchJson<ListResponse<Run>>("/api/runs");
  },
  async getRun(runId: string) {
    return fetchJson<Run>(`/api/runs/${runId}`);
  },
  async getRunArtifacts(runId: string) {
    return fetchJson<ArtifactList>(`/api/runs/${runId}/artifacts`);
  },
  async getRunTrace(runId: string) {
    return fetchJson<TraceList>(`/api/runs/${runId}/trace`);
  },
  runReportUrl(runId: string, format: "json" | "html" | "pdf") {
    return `${API_BASE_URL}/api/runs/${runId}/report?format=${format}`;
  },
  scenarioStatusReportUrl() {
    return `${API_BASE_URL}/api/scenarios/status-report.html`;
  },
  async getSettings() {
    return fetchJson<RuntimeSettings>("/api/settings");
  },
  async updateSettings(patch: RuntimeSettingsPatch) {
    return fetchJson<RuntimeSettings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  async getDoctor() {
    return fetchJson<DoctorResponse>("/api/doctor");
  },
  async startManualPipeline(payload: ManualPipelineStartPayload = {}) {
    return fetchJson<PipelineStartResponse>("/api/pipeline/manual-to-scenarios", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async getJob(jobId: string) {
    return fetchJson<Job>(`/api/jobs/${jobId}`);
  },
};
