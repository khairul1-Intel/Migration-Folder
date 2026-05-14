from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import subprocess
import sys

from sync_common import (
    ALLOWED_DESTINATIONS,
    ALLOWED_SOURCES,
    FIRST_TIME_REPORT_FILE_NAME,
    ROBOCOPY_SUCCESS_THRESHOLD,
    append_report_block,
    build_robocopy_command,
    extract_itemized_changes,
    format_change_list,
    format_destination_options,
    format_source_options,
    get_config_source_and_destination,
    normalize_allowed_value,
    parse_robocopy_summary_from_text,
    quote_arg,
    resolve_report_dir,
    validate_sync_safety,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a one-time full 1:1 mirror copy with robocopy."
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Source folder path. Must be one of the allowed CDC source paths.",
    )
    parser.add_argument(
        "--destination",
        default=None,
        help="Destination folder path. Must be E:\\Production or E:\\Development.",
    )
    parser.add_argument(
        "--list-destinations",
        action="store_true",
        help="Print allowed destination paths and exit.",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Print allowed source paths and exit.",
    )
    parser.add_argument(
        "--report-dir",
        default=".",
        help="Directory where generated report files are stored.",
    )
    parser.add_argument("--retries", type=int, default=3, help="Robocopy retry count.")
    parser.add_argument(
        "--wait-seconds", type=int, default=10, help="Wait time between retries."
    )
    parser.add_argument(
        "--threads", type=int, default=16, help="Robocopy multi-thread count (1-128)."
    )
    return parser.parse_args()


def resolve_source_and_destination(args: argparse.Namespace) -> tuple[str, str]:
    config_source, config_destination = get_config_source_and_destination(__file__)

    source = normalize_allowed_value(
        args.source or config_source,
        ALLOWED_SOURCES,
        "source",
    )
    destination = normalize_allowed_value(
        args.destination or config_destination,
        ALLOWED_DESTINATIONS,
        "destination",
    )

    validate_sync_safety(source, destination)
    return source, destination


def main() -> int:
    args = parse_args()

    if args.list_sources:
        print(format_source_options())
        return 0

    if args.list_destinations:
        print(format_destination_options())
        return 0

    try:
        source, destination = resolve_source_and_destination(args)
    except ValueError as exc:
        print(exc)
        return 1

    source_path = Path(source)
    if not source_path.exists():
        print(f"Source path does not exist or is unreachable: {source}")
        return 1

    report_dir = resolve_report_dir(__file__, args.report_dir)
    report_file = report_dir / FIRST_TIME_REPORT_FILE_NAME

    try:
        command = build_robocopy_command(
            source=source,
            destination=destination,
            retries=args.retries,
            wait_seconds=args.wait_seconds,
            threads=args.threads,
        )
    except ValueError as exc:
        print(exc)
        return 1

    printable_command = " ".join(quote_arg(part) for part in command)

    print("Starting one-time full mirror copy...")
    print(f"Source      : {source}")
    print(f"Destination : {destination}")
    print(f"Command     : {printable_command}")

    completed = subprocess.run(command, check=False, capture_output=True, text=True, errors="replace")

    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    output_text = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    summary = parse_robocopy_summary_from_text(output_text)
    added_or_updated, deleted_from_destination = extract_itemized_changes(output_text)

    robocopy_code = completed.returncode
    status = "success" if robocopy_code < ROBOCOPY_SUCCESS_THRESHOLD else "failure"
    now = dt.datetime.now()

    block_lines = [
        "=== FIRST_TIME_SETUP ===",
        f"time: {now:%Y-%m-%d %H:%M:%S}",
        f"source: {source}",
        f"destination: {destination}",
        f"robocopy_exit_code: {robocopy_code}",
        f"status: {status}",
        f"files_added_or_updated_count: {summary['files_copied']}",
        f"files_deleted_from_destination_count: {summary['deleted_items']}",
        *format_change_list("added_or_updated:", added_or_updated),
        *format_change_list("deleted_from_destination:", deleted_from_destination),
    ]
    append_report_block(report_file, block_lines)
    print(f"First-time report file: {report_file}")

    if robocopy_code >= ROBOCOPY_SUCCESS_THRESHOLD:
        print(f"robocopy failed with exit code {robocopy_code}.")
        return 1

    print("Full mirror setup completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
