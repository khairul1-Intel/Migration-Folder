# Robocopy Migration (2 Generated Files Only)

This setup runs strict source-to-destination mirror and generates only 2 report files:

1. `first_time_setup_report.txt`
2. `daily_update_history.txt`

No per-run timestamp log file is generated.

## Safety Rules

- Source is always read from approved UNC source list.
- Destination is only `E:\Production` or `E:\Development`.
- Source and destination cannot be the same path.
- Source delete/move switches (`/MOV`, `/MOVE`) are blocked.
- Mirror mode is strict (`/MIR`) so deletes happen only on destination extras.

## Configure Source and Destination

Edit `config.yaml` and keep one active source and one active destination:

```yaml
# Keep only one source active at a time.
source: \\ccedap802.cdcprod.mfg.intel.com\E$\Production
# source: \\ccedap802.cdcprod.mfg.intel.com\F$\Development

# Keep only one destination active at a time.
destination: E:\Production
# destination: E:\Development
```

## Run Commands

First-time setup:

```powershell
py -3 .\first_time_full_copy.py
```

Daily update:

```powershell
py -3 .\daily_mirror.py
```

Task Scheduler can call:

- `run_daily_mirror.bat`

## Exactly What Files Are Generated

First-time run writes:

- `first_time_setup_report.txt`

Daily run writes/appends:

- `daily_update_history.txt`

Notes:

- `first_time_setup_report.txt` uses append blocks (usually one block because first-time run is one-time).
- `daily_update_history.txt` appends one block per daily run.

## File Content Examples

Example `first_time_setup_report.txt` block:

```text
=== FIRST_TIME_SETUP ===
time: 2026-05-14 06:01:05
source: \\ccedap802.cdcprod.mfg.intel.com\E$\Production
destination: E:\Production
robocopy_exit_code: 1
status: success
files_added_or_updated_count: 27
files_deleted_from_destination_count: 3
added_or_updated:
- New File       1024    folderA\file1.txt
- Newer          2048    folderB\file2.ini
deleted_from_destination:
- *EXTRA File            folderC\old.txt
- *EXTRA Dir             folderD
```

Example `daily_update_history.txt` block:

```text
=== DAILY_UPDATE ===
time: 2026-05-15 06:00:02
source: \\ccedap802.cdcprod.mfg.intel.com\E$\Production
destination: E:\Production
robocopy_exit_code: 1
status: success
files_added_or_updated_count: 4
files_deleted_from_destination_count: 1
added_or_updated:
- Newer          4096    reports\today.csv
deleted_from_destination:
- *EXTRA File            temp\old.log
```

## Exit Code Handling

- robocopy `< 8` is treated as success
- robocopy `>= 8` is treated as failure
