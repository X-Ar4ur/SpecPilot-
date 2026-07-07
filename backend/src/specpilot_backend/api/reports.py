from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{report_id}")
def get_report(report_id: str) -> dict[str, object]:
    return {
        "report_id": report_id,
        "report_json": f"/api/reports/{report_id}/report.json",
        "report_html": f"/api/reports/{report_id}/report.html",
    }
