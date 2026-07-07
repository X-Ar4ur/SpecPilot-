export type FeatureModule =
  | "Project"
  | "Board"
  | "List"
  | "Card"
  | "Views"
  | "Settings"
  | "Admin"
  | "Other";

export type CoverageStatus = "uncovered" | "covered" | "partial";

export type Feature = {
  feature_id: string;
  module: FeatureModule;
  title: string;
  summary: string;
  source_urls: string[];
  evidence_quotes: string[];
  confidence: number;
  coverage_status: CoverageStatus;
};

export type Priority = "P0" | "P1" | "P2";
export type Difficulty = "simple" | "medium" | "hard";
export type ReviewStatus = "auto_validated" | "needs_review" | "rejected";
export type RunStatus =
  | "queued"
  | "running"
  | "pass"
  | "fail"
  | "needs_review"
  | "cancelled"
  | "error";
export type RunVerdict = "pass" | "fail" | "needs_review";
export type ExpectationType =
  | "element_visible"
  | "text_present"
  | "url_match"
  | "element_state"
  | "containment"
  | "semantic";

export type TestStep = {
  order: number;
  action: string;
};

export type Expectation = {
  type: ExpectationType;
  description: string;
  params: Record<string, unknown>;
};

export type ScenarioSummary = {
  scenario_id: string;
  feature_id: string;
  title: string;
  priority: Priority;
  difficulty: Difficulty;
  review_status: ReviewStatus;
  latest_result?: RunVerdict | null;
  is_mutation: boolean;
};

export type TestScenario = ScenarioSummary & {
  source_urls: string[];
  evidence_quotes: string[];
  preconditions: string[];
  test_data: Record<string, unknown>;
  steps: TestStep[];
  expectations: Expectation[];
  max_steps: number;
  requires_visual_check: boolean;
};

export type Run = {
  run_id: string;
  scenario_ids: string[];
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  verdict: RunVerdict | null;
  failure_primary: string | null;
  failure_secondary: string[];
  artifact_dir: string;
  report_id: string | null;
  verification_results?: unknown[];
  failure_classification?: unknown;
  report_links?: Record<string, string>;
};

export type RuntimeSettings = {
  models: {
    text_llm_provider: "openai_compatible" | "deepseek" | "browser_use";
    openai_compatible_provider_name: string;
    openai_compatible_home_url: string;
    openai_compatible_base_url: string;
    openai_compatible_model: string;
    openai_compatible_note: string | null;
    openai_compatible_api_key_configured: boolean;
    deepseek_model: string;
    deepseek_api_key_configured: boolean;
    browser_use_model: string;
    browser_use_api_key_configured: boolean;
    browser_use_llm_fallback_enabled: boolean;
    browser_use_cloud_browser_enabled: boolean;
    glm_vision_model: string;
    glm_api_key_configured: boolean;
  };
};

export type RuntimeSettingsPatch = {
  models: {
    text_llm_provider?: "openai_compatible" | "deepseek" | "browser_use";
    openai_compatible_provider_name?: string;
    openai_compatible_home_url?: string;
    openai_compatible_base_url?: string;
    openai_compatible_api_key?: string | null;
    openai_compatible_model?: string;
    openai_compatible_note?: string | null;
    deepseek_model?: string;
    deepseek_api_key?: string | null;
    browser_use_model?: string;
    browser_use_api_key?: string | null;
    browser_use_llm_fallback_enabled?: boolean;
    browser_use_cloud_browser_enabled?: false;
    glm_vision_model?: string;
    glm_api_key?: string | null;
  };
};

export type DoctorCheckStatus = "ok" | "warning" | "error";

export type DoctorCheck = {
  status: DoctorCheckStatus;
  detail: string;
};

export type DoctorResponse = {
  status: DoctorCheckStatus;
  checks: Record<string, DoctorCheck>;
};

export type ListResponse<T> = {
  items: T[];
};

export type CreateRunResponse = {
  run_id: string;
  status: "queued";
  live_url: string;
};

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type ManualPipelineResult = {
  crawl_id?: string;
  index_id?: string;
  pages_count?: number;
  chunks_count?: number;
  features_count?: number;
  scenarios_count?: number;
  pages?: ManualPipelinePage[];
  features?: Feature[];
  warnings?: ManualPipelineWarning[];
  zero_locator?: boolean;
  replaced_existing?: boolean;
};

export type ManualPipelineStartStage =
  | "crawl"
  | "index"
  | "features"
  | "scenarios";

export type ManualPipelinePage = {
  title: string;
  url: string;
  manual_section: string;
  module: string;
};

export type ManualPipelineWarning = {
  stage: string;
  scope: string;
  message: string;
};

export type ManualPipelineStartPayload = {
  start_stage?: ManualPipelineStartStage;
  resume_from_job_id?: string;
  crawl_id?: string;
  index_id?: string;
  feature_ids?: string[];
};

export type Job = {
  job_id: string;
  job_type: string;
  status: JobStatus;
  stage: string;
  progress: number;
  message: string | null;
  result: ManualPipelineResult | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type PipelineStartResponse = {
  job_id: string;
  status: "queued";
};

export type TraceEventType =
  | "node_status"
  | "browser_step"
  | "browser_frame"
  | "verification"
  | "classification"
  | "repair"
  | "report"
  | "error";

export type TraceEvent = {
  event_id: string;
  run_id: string;
  ts: string;
  type: TraceEventType;
  node: string | null;
  status: string | null;
  message: string | null;
  payload: Record<string, unknown>;
};

export type TraceList = {
  items: TraceEvent[];
};

export type ArtifactList = {
  run_id: string;
  files: string[];
};

export type FixtureKind = "project" | "board" | "list" | "card";
export type DataDependency = "none" | "self_seeding" | "interactive";

export type InventoryCard = { id: string; name: string };
export type InventoryList = { id: string; name: string; cards: InventoryCard[] };
export type InventoryBoard = { id: string; name: string; lists: InventoryList[] };
export type InventoryProject = {
  id: string;
  name: string;
  boards: InventoryBoard[];
};
export type FixtureInventory = {
  target_app_url: string;
  projects: InventoryProject[];
};

export type ScenarioFixtureBinding = {
  scenario_id: string;
  target_app_url: string;
  ref: string;
  entity_kind: FixtureKind;
  entity_id: string;
  resolved_values: Record<string, unknown>;
  created_by_specpilot: boolean;
  bound_at: string;
};

export type FixtureSlotBindingState = {
  ref: string;
  kind: FixtureKind;
  bound: boolean;
  exists: boolean;
  binding: ScenarioFixtureBinding | null;
};

export type ScenarioBindingStatus = {
  scenario_id: string;
  target_app_url: string;
  data_dependency: DataDependency;
  ready: boolean;
  slots: FixtureSlotBindingState[];
};

export type FixtureBindRequest = {
  scenario_id: string;
  ref: string;
  mode: "existing" | "create";
  kind: FixtureKind;
  entity_id?: string;
  parent_id?: string;
  attributes?: Record<string, unknown>;
};

export type BoundingBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type BrowserFrame = {
  eventId: string;
  ts: string;
  src: string;
  artifactPath?: string;
  url?: string;
  step?: number;
  action?: string;
  targetBox?: BoundingBox;
};
