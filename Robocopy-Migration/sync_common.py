from __future__ import annotations

from pathlib import Path
import re


ROBOCOPY_SUCCESS_THRESHOLD = 8
FIRST_TIME_REPORT_FILE_NAME = "first_time_setup_report.txt"
DAILY_HISTORY_FILE_NAME = "daily_update_history.txt"

CONFIG_FILE_NAME = "config.yaml"
REQUIRED_CONFIG_KEYS = ("source", "destination")
ALLOWED_SOURCES = (
    r"\\ccedap801.cdcprod.mfg.intel.com\E$\Production",
    r"\\ccedap801.cdcprod.mfg.intel.com\F$\Development",
    r"\\ccedap802.cdcprod.mfg.intel.com\E$\Production",
    r"\\ccedap802.cdcprod.mfg.intel.com\F$\Development",
    r"\\ccedap803.cdcprod.mfg.intel.com\E$\Production",
    r"\\ccedap803.cdcprod.mfg.intel.com\F$\Development",
)
ALLOWED_DESTINATIONS = (r"E:\Production", r"E:\Development")

FORBIDDEN_ROBOCOPY_SWITCHES = {"/MOVE", "/MOV"}


def normalize_allowed_value(value: str, allowed_values: tuple[str, ...], field_name: str) -> str:
    allowed_norm = {item.lower(): item for item in allowed_values}
    value_norm = value.lower()
    if value_norm not in allowed_norm:
        allowed_text = ", ".join(allowed_values)
        raise ValueError(
            f"Invalid {field_name} '{value}'. Allowed {field_name} values: {allowed_text}"
        )
    return allowed_norm[value_norm]


def format_options(header_name: str, options: tuple[str, ...]) -> str:
    lines = [header_name]
    lines.extend(options)
    return "\n".join(lines)


def format_source_options() -> str:
    return format_options("allowed_source", ALLOWED_SOURCES)


def format_destination_options() -> str:
    return format_options("allowed_destination", ALLOWED_DESTINATIONS)


def get_config_path(script_file: str) -> Path:
    return Path(script_file).resolve().parent / CONFIG_FILE_NAME


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    chars: list[str] = []

    for char in value:
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None

        if char == "#" and quote is None:
            break

        chars.append(char)

    return "".join(chars).strip()


def validate_sync_safety(source: str, destination: str) -> None:
    if source.lower() == destination.lower():
        raise ValueError("Source and destination cannot be the same path.")

    if not source.startswith("\\\\"):
        raise ValueError("Source must be a UNC path from the allowed source list.")

    destination_path = Path(destination)
    if not destination_path.is_absolute():
        raise ValueError("Destination must be an absolute local path.")


def load_config_values(config_path: Path) -> dict[str, str]:
    if not config_path.exists():
        raise ValueError(f"Config file not found: {config_path}")

    values: dict[str, str] = {}
    seen_required_keys: set[str] = set()

    with config_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue

            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = _strip_quotes(_strip_inline_comment(raw_value))

            if key in REQUIRED_CONFIG_KEYS and key in seen_required_keys:
                raise ValueError(
                    f"Multiple active '{key}' entries in {config_path} at line {line_number}. "
                    "Keep only one active entry."
                )

            values[key] = value
            if key in REQUIRED_CONFIG_KEYS:
                seen_required_keys.add(key)

    missing = [key for key in REQUIRED_CONFIG_KEYS if not values.get(key)]
    if missing:
        missing_keys = ", ".join(missing)
        raise ValueError(f"Missing required config key(s): {missing_keys}")

    values["source"] = normalize_allowed_value(values["source"], ALLOWED_SOURCES, "source")
    values["destination"] = normalize_allowed_value(
        values["destination"], ALLOWED_DESTINATIONS, "destination"
    )

    validate_sync_safety(values["source"], values["destination"])
    return values


def get_config_source_and_destination(script_file: str) -> tuple[str, str]:
    values = load_config_values(get_config_path(script_file))
    return values["source"], values["destination"]


def resolve_report_dir(script_file: str, report_dir_arg: str) -> Path:
    script_dir = Path(script_file).resolve().parent
    report_dir = Path(report_dir_arg)
    if not report_dir.is_absolute():
        report_dir = script_dir / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def quote_arg(value: str) -> str:
    return f'"{value}"' if " " in value else value


def parse_robocopy_summary_from_text(output_text: str) -> dict[str, str]:
    summary = {
        "files_copied": "0",
        "files_extras": "0",
        "dirs_extras": "0",
        "deleted_items": "0",
    }

    row_pattern = re.compile(r"^(Dirs|Files)\s*:\s*(.*)$")

    for line in output_text.splitlines():
        match = row_pattern.match(line.strip())
        if not match:
            continue

        label = match.group(1)
        values = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", match.group(2))]
        if len(values) < 6:
            continue

        if label == "Files":
            summary["files_copied"] = str(values[1])
            summary["files_extras"] = str(values[5])
        if label == "Dirs":
            summary["dirs_extras"] = str(values[5])

    files_extras = int(summary["files_extras"])
    dirs_extras = int(summary["dirs_extras"])
    summary["deleted_items"] = str(files_extras + dirs_extras)
    return summary


def extract_itemized_changes(output_text: str) -> tuple[list[str], list[str]]:
    added_or_updated: list[str] = []
    deleted_from_destination: list[str] = []

    add_pattern = re.compile(r"^(New File|New Dir|Newer|Older|Changed|Tweaked)\b", re.IGNORECASE)
    delete_pattern = re.compile(r"^\*?EXTRA (File|Dir)\b", re.IGNORECASE)

    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if delete_pattern.match(line):
            deleted_from_destination.append(line)
            continue

        if add_pattern.match(line):
            added_or_updated.append(line)

    return added_or_updated, deleted_from_destination


def format_change_list(title: str, items: list[str]) -> list[str]:
    lines = [title]
    if not items:
        lines.append("- none")
        return lines

    for item in items:
        lines.append(f"- {item}")
    return lines


def append_report_block(report_file: Path, block_lines: list[str]) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with report_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(block_lines))
        handle.write("\n\n")


def assert_robocopy_command_is_safe(command: list[str]) -> None:
    switches = {token.upper() for token in command if token.startswith("/")}

    forbidden = switches.intersection(FORBIDDEN_ROBOCOPY_SWITCHES)
    if forbidden:
        forbidden_text = ", ".join(sorted(forbidden))
        raise ValueError(f"Unsafe robocopy switch detected: {forbidden_text}")

    if "/MIR" not in switches:
        raise ValueError("robocopy command must include /MIR for strict destination mirror behavior.")


def build_robocopy_command(
    source: str,
    destination: str,
    retries: int,
    wait_seconds: int,
    threads: int,
) -> list[str]:
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if wait_seconds < 0:
        raise ValueError("wait_seconds must be >= 0")
    if not 1 <= threads <= 128:
        raise ValueError("threads must be between 1 and 128")

    command = [
        "robocopy",
        source,
        destination,
        "/MIR",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/Z",
        "/FFT",
        "/XJ",
        f"/R:{retries}",
        f"/W:{wait_seconds}",
        f"/MT:{threads}",
    ]

    assert_robocopy_command_is_safe(command)
    return command
