from __future__ import annotations

from pathlib import Path


def write_env_values(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
    seen: set[str] = set()
    rewritten: list[str] = []

    for line in lines:
        key = _line_key(line)
        if key is None or key not in updates:
            rewritten.append(line)
            continue
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        rewritten.append(f"{key}={_format_env_value(updates[key])}{newline}")
        seen.add(key)

    if rewritten and not rewritten[-1].endswith(("\n", "\r\n")):
        rewritten[-1] += "\n"

    for key, value in updates.items():
        if key not in seen:
            rewritten.append(f"{key}={_format_env_value(value)}\n")

    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text("".join(rewritten), encoding="utf-8")
    temp_path.replace(path)


def _line_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    if not key or any(char.isspace() for char in key):
        return None
    return key


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(char.isspace() for char in value) or "#" in value or '"' in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
