import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Field, Session, SQLModel, create_engine, select

from specpilot_backend.config import get_settings


class FeatureRecord(SQLModel, table=True):
    feature_id: str = Field(primary_key=True)
    payload_json: str


class ScenarioRecord(SQLModel, table=True):
    scenario_id: str = Field(primary_key=True)
    feature_id: str = Field(index=True)
    review_status: str = Field(index=True)
    priority: str = Field(index=True)
    difficulty: str = Field(index=True)
    is_mutation: bool = Field(default=False, index=True)
    latest_result: str | None = None
    payload_json: str


class JobRecord(SQLModel, table=True):
    job_id: str = Field(primary_key=True)
    job_type: str = Field(index=True)
    status: str = Field(index=True)
    stage: str
    progress: int = Field(default=0, ge=0, le=100)
    message: str | None = None
    result_json: str | None = None
    error: str | None = None
    created_at: str = Field(index=True)
    started_at: str | None = None
    finished_at: str | None = None


class RunRecord(SQLModel, table=True):
    run_id: str = Field(primary_key=True)
    status: str = Field(index=True)
    artifact_dir: str
    payload_json: str
    created_at: str = Field(index=True)


class FixtureBindingRecord(SQLModel, table=True):
    scenario_id: str = Field(primary_key=True)
    target_app_url: str = Field(primary_key=True)
    ref: str = Field(primary_key=True)
    entity_kind: str
    entity_id: str
    resolved_values_json: str
    created_by_specpilot: bool = Field(default=False)
    bound_at: str


def _database_url() -> str:
    return get_settings().database_url


engine: Engine = create_engine(
    _database_url(), connect_args={"check_same_thread": False}
)


def configure_database(database_url: str) -> None:
    global engine
    _ensure_sqlite_parent_dir(database_url)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})


def create_tables() -> None:
    _ensure_sqlite_parent_dir(str(engine.url))
    SQLModel.metadata.create_all(engine)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return
    if url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def save_feature_payload(payload: dict[str, object]) -> None:
    with Session(engine) as session:
        record = FeatureRecord(
            feature_id=str(payload["feature_id"]),
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        session.merge(record)
        session.commit()


def list_feature_payloads() -> list[dict[str, object]]:
    with Session(engine) as session:
        records = session.exec(select(FeatureRecord)).all()
        return [json.loads(record.payload_json) for record in records]


def clear_feature_payloads() -> None:
    with Session(engine) as session:
        for record in session.exec(select(FeatureRecord)).all():
            session.delete(record)
        session.commit()


def save_scenario_payload(payload: dict[str, object]) -> None:
    latest_result_value = payload.get("latest_result")
    latest_result = (
        latest_result_value if isinstance(latest_result_value, str) else None
    )
    with Session(engine) as session:
        record = ScenarioRecord(
            scenario_id=str(payload["scenario_id"]),
            feature_id=str(payload["feature_id"]),
            review_status=str(payload["review_status"]),
            priority=str(payload["priority"]),
            difficulty=str(payload["difficulty"]),
            is_mutation=bool(payload.get("is_mutation", False)),
            latest_result=latest_result,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        session.merge(record)
        session.commit()


def clear_non_mutation_scenario_payloads() -> None:
    with Session(engine) as session:
        records = session.exec(select(ScenarioRecord)).all()
        for record in records:
            if not record.is_mutation:
                session.delete(record)
        session.commit()


def list_scenario_records(
    *,
    feature_id: str | None = None,
    priority: str | None = None,
    difficulty: str | None = None,
    review_status: str | None = None,
    latest_result: str | None = None,
    is_mutation: bool | None = None,
) -> list[ScenarioRecord]:
    statement = select(ScenarioRecord)
    if feature_id is not None:
        statement = statement.where(ScenarioRecord.feature_id == feature_id)
    if priority is not None:
        statement = statement.where(ScenarioRecord.priority == priority)
    if difficulty is not None:
        statement = statement.where(ScenarioRecord.difficulty == difficulty)
    if review_status is not None:
        statement = statement.where(ScenarioRecord.review_status == review_status)
    if latest_result is not None:
        statement = statement.where(ScenarioRecord.latest_result == latest_result)
    if is_mutation is not None:
        statement = statement.where(ScenarioRecord.is_mutation == is_mutation)
    with Session(engine) as session:
        return list(session.exec(statement).all())


def get_scenario_payload(scenario_id: str) -> dict[str, object] | None:
    with Session(engine) as session:
        record = session.get(ScenarioRecord, scenario_id)
        if record is None:
            return None
        return json.loads(record.payload_json)


def update_scenario_latest_result(
    scenario_id: str,
    latest_result: str | None,
) -> bool:
    with Session(engine) as session:
        record = session.get(ScenarioRecord, scenario_id)
        if record is None:
            return False
        record.latest_result = latest_result
        session.add(record)
        session.commit()
        return True


def create_job_record(
    *,
    job_type: str,
    stage: str,
    message: str | None = None,
    result: dict[str, object] | None = None,
) -> JobRecord:
    from specpilot_backend.ids import new_id

    now = datetime.now(UTC).isoformat()
    record = JobRecord(
        job_id=new_id("job"),
        job_type=job_type,
        status="queued",
        stage=stage,
        progress=0,
        message=message,
        result_json=json.dumps(result, ensure_ascii=False) if result is not None else None,
        created_at=now,
    )
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def update_job_record(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> JobRecord | None:
    now = datetime.now(UTC).isoformat()
    with Session(engine) as session:
        record = session.get(JobRecord, job_id)
        if record is None:
            return None
        if status is not None:
            if status == "running" and record.started_at is None:
                record.started_at = now
            if status in {"succeeded", "failed", "cancelled"}:
                record.finished_at = now
            record.status = status
        if stage is not None:
            record.stage = stage
        if progress is not None:
            record.progress = max(0, min(100, progress))
        if message is not None:
            record.message = message
        if result is not None:
            record.result_json = json.dumps(result, ensure_ascii=False)
        if error is not None:
            record.error = error
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_job_payload(job_id: str) -> dict[str, object] | None:
    with Session(engine) as session:
        record = session.get(JobRecord, job_id)
        if record is None:
            return None
        return _job_record_to_payload(record)


def _job_record_to_payload(record: JobRecord) -> dict[str, object]:
    return {
        "job_id": record.job_id,
        "job_type": record.job_type,
        "status": record.status,
        "stage": record.stage,
        "progress": record.progress,
        "message": record.message,
        "result": json.loads(record.result_json) if record.result_json else None,
        "error": record.error,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
    }


def save_run_payload(payload: dict[str, object]) -> None:
    with Session(engine) as session:
        run_id = str(payload["run_id"])
        existing = session.get(RunRecord, run_id)
        created_at = existing.created_at if existing is not None else datetime.now(UTC).isoformat()
        record = RunRecord(
            run_id=run_id,
            status=str(payload["status"]),
            artifact_dir=str(payload["artifact_dir"]),
            payload_json=json.dumps(payload, ensure_ascii=False),
            created_at=created_at,
        )
        session.merge(record)
        session.commit()


def mark_orphaned_running_runs_cancelled(active_run_ids: set[str]) -> int:
    finished_at = datetime.now(UTC).isoformat()
    changed = 0
    statement = select(RunRecord).where(RunRecord.status == "running")
    with Session(engine) as session:
        records = session.exec(statement).all()
        for record in records:
            if record.run_id in active_run_ids:
                continue
            payload = json.loads(record.payload_json)
            if payload.get("status") != "running":
                continue
            payload["status"] = "cancelled"
            payload["finished_at"] = payload.get("finished_at") or finished_at
            payload["duration_ms"] = payload.get("duration_ms")
            payload["verdict"] = None
            payload["failure_primary"] = payload.get("failure_primary") or "interrupted"
            record.status = "cancelled"
            record.payload_json = json.dumps(payload, ensure_ascii=False)
            changed += 1
        if changed:
            session.commit()
    return changed


def list_run_payloads() -> list[dict[str, object]]:
    statement = select(RunRecord).order_by(desc(RunRecord.created_at))
    with Session(engine) as session:
        records = session.exec(statement).all()
        return [json.loads(record.payload_json) for record in records]


def get_run_payload(run_id: str) -> dict[str, object] | None:
    with Session(engine) as session:
        record = session.get(RunRecord, run_id)
        if record is None:
            return None
        return json.loads(record.payload_json)


def artifact_path_for_run(run_id: str) -> Path:
    run = get_run_payload(run_id)
    if run is None:
        return get_settings().artifact_root / run_id
    return Path(str(run["artifact_dir"]))


def save_fixture_binding(payload: dict[str, object]) -> None:
    with Session(engine) as session:
        record = FixtureBindingRecord(
            scenario_id=str(payload["scenario_id"]),
            target_app_url=str(payload["target_app_url"]),
            ref=str(payload["ref"]),
            entity_kind=str(payload["entity_kind"]),
            entity_id=str(payload["entity_id"]),
            resolved_values_json=json.dumps(
                payload.get("resolved_values", {}), ensure_ascii=False
            ),
            created_by_specpilot=bool(payload.get("created_by_specpilot", False)),
            bound_at=str(payload["bound_at"]),
        )
        session.merge(record)
        session.commit()


def list_fixture_bindings(
    scenario_id: str, target_app_url: str
) -> list[dict[str, object]]:
    statement = select(FixtureBindingRecord).where(
        FixtureBindingRecord.scenario_id == scenario_id,
        FixtureBindingRecord.target_app_url == target_app_url,
    )
    with Session(engine) as session:
        return [
            _fixture_binding_to_payload(record)
            for record in session.exec(statement).all()
        ]


def get_fixture_binding(
    scenario_id: str, target_app_url: str, ref: str
) -> dict[str, object] | None:
    with Session(engine) as session:
        record = session.get(
            FixtureBindingRecord, (scenario_id, target_app_url, ref)
        )
        if record is None:
            return None
        return _fixture_binding_to_payload(record)


def _fixture_binding_to_payload(
    record: FixtureBindingRecord,
) -> dict[str, object]:
    return {
        "scenario_id": record.scenario_id,
        "target_app_url": record.target_app_url,
        "ref": record.ref,
        "entity_kind": record.entity_kind,
        "entity_id": record.entity_id,
        "resolved_values": json.loads(record.resolved_values_json),
        "created_by_specpilot": record.created_by_specpilot,
        "bound_at": record.bound_at,
    }
