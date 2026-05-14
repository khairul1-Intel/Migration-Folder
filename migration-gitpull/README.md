# Multi-Repo Git Pull Utility

This project contains a Python script that scans a root folder containing many repository folders and pulls the latest changes for each repository.

The script is branch-safe for development workflows:
- It always pulls the currently checked-out branch in each repo.
- It does not switch branches.
- It does not force pull from main.

## File

- pull_all_repos.py

## What It Does

1. Validates that Git is installed and available in PATH.
2. Validates the root folder.
3. Scans folders under the root.
4. Detects whether each folder is a Git repository.
5. Reads the current branch for each repository.
6. Resolves pull target as remote/current-branch.
7. Runs a fast-forward-only pull.
8. Prints per-folder results and a final summary.

## Requirements

- Python 3.9 or later
- Git installed and available in PATH

## Usage

Run from this folder or provide full path to the script.

    python pull_all_repos.py "C:/path/to/root-folder"

Top-level folders only (default behavior):

    python pull_all_repos.py "C:/path/to/root-folder"

Recursive scan of all nested folders:

    python pull_all_repos.py "C:/path/to/root-folder" --recurse

Include the root folder itself as a candidate repository:

    python pull_all_repos.py "C:/path/to/root-folder" --include-root

Combine both options:

    python pull_all_repos.py "C:/path/to/root-folder" --recurse --include-root

## CLI Arguments

- root_path (optional)
  - Root folder containing repository folders.
  - Default is current directory.

- --recurse
  - Scan all nested folders under the root.

- --include-root
  - Also treat the root folder itself as a repository candidate.

## Pull Target Rules

For each repository:

1. Get current branch name.
2. Read configured remote for that branch from Git config.
3. If no remote is configured, fallback to origin.
4. Pull only remote/current-branch with --ff-only.

Example:
- If current branch is feature/abc, it pulls feature/abc.
- If current branch is release/v2, it pulls release/v2.

## Output Behavior

For every scanned folder, the script prints:
- scan position (example: SCAN 5/42)
- whether repo was detected
- branch and pull target
- success, skip reason, or detailed error

Final summary includes:
- Scanned folders
- Git repos found
- Non-git folders
- Pulled
- Skipped
- Failed

## Error Handling and Specific Messages

The script reports specific causes when possible, including:

- No Git work tree found in this folder
- Failed to read current branch
- Detached HEAD or unknown branch
- Remote is not configured in this repository
- Access or authentication failed while pulling
- Network/connectivity issue while reaching remote
- Remote branch does not exist
- Cannot fast-forward because branches diverged
- Local uncommitted changes would be overwritten
- Pull failed with original Git fatal or error message

This helps quickly identify whether the issue is repo setup, credentials, connectivity, or branch state.

## Exit Codes

- 0: Completed without pull failures
  - Includes cases where some folders are skipped

- 1: Error state
  - Git not installed
  - Invalid root path
  - One or more repositories failed to pull

## Typical Use Cases

1. Daily update of many repositories in one parent folder.
2. Mixed branch development where each repo is on a different branch.
3. Quick scan to identify repos with pull/auth/network issues.
