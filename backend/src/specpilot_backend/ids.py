from uuid import uuid4

ID_PREFIXES = {
    "ft": "ft_",
    "sc": "sc_",
    "run": "run_",
    "crawl": "crawl_",
    "idx": "idx_",
    "job": "job_",
    "evt": "evt_",
}


def new_id(prefix: str) -> str:
    try:
        resolved_prefix = ID_PREFIXES[prefix]
    except KeyError as exc:
        supported = ", ".join(sorted(ID_PREFIXES))
        msg = f"Unsupported id prefix {prefix!r}; expected one of: {supported}"
        raise ValueError(msg) from exc
    return f"{resolved_prefix}{uuid4().hex}"


def new_event_id() -> str:
    return new_id("evt")
