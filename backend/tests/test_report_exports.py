from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from specpilot_backend.config import Settings
from specpilot_backend.main import app
from specpilot_backend.services import persistence


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    tmp_path = Path(".pytest_cache") / "specpilot-report-export-tests" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'specpilot.db'}",
        artifact_root=tmp_path / "runs",
        chroma_persist_dir=tmp_path / "chroma",
    )
    monkeypatch.setattr("specpilot_backend.api.runs.get_settings", lambda: settings)
    monkeypatch.setattr(
        "specpilot_backend.services.artifacts.get_settings", lambda: settings
    )
    persistence.configure_database(settings.database_url)
    persistence.create_tables()
    with TestClient(app) as test_client:
        yield test_client


def test_run_report_export_serves_json_and_html(client: TestClient) -> None:
    run = client.post(
        "/api/runs",
        json={"scenario_ids": ["sc_create_card_001"], "mode": "single", "config": {}},
    ).json()
    artifact_dir = Path(client.get(f"/api/runs/{run['run_id']}").json()["artifact_dir"])
    (artifact_dir / "report.json").write_text('{"run_id":"run_export"}', encoding="utf-8")
    (artifact_dir / "report.html").write_text("<html>report</html>", encoding="utf-8")

    json_response = client.get(f"/api/runs/{run['run_id']}/report?format=json")
    html_response = client.get(f"/api/runs/{run['run_id']}/report?format=html")
    missing_pdf = client.get(f"/api/runs/{run['run_id']}/report?format=pdf")

    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")
    assert html_response.status_code == 200
    assert html_response.headers["content-type"].startswith("text/html")
    assert missing_pdf.status_code == 404
