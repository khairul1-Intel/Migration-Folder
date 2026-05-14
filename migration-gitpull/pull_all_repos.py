import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run_git(repo_path: Path, *git_args: str, quiet: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(repo_path), *git_args]

    if capture:
        return subprocess.run(command, check=False, text=True, capture_output=True)

    if quiet:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return subprocess.run(command, check=False)


def best_git_message(stdout: str, stderr: str) -> str:
    combined = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
    if not combined:
        return ""

    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("fatal:") or lowered.startswith("error:"):
            return line
    return lines[0]


def get_repo_status(path: Path) -> tuple[bool, str]:
    result = run_git(path, "rev-parse", "--is-inside-work-tree", capture=True)
    if result.returncode == 0:
        return True, ""

    message = best_git_message(result.stdout, result.stderr)
    lowered = message.lower()
    if "not a git repository" in lowered:
        return False, "No Git work tree found in this folder."
    if message:
        return False, f"Git repo check failed: {message}"
    return False, "Git repo check failed with unknown error."


def get_current_branch(path: Path) -> tuple[str, str]:
    result = run_git(path, "branch", "--show-current", capture=True)
    if result.returncode != 0:
        message = best_git_message(result.stdout, result.stderr)
        if message:
            return "", f"Failed to read current branch: {message}"
        return "", "Failed to read current branch."

    branch = result.stdout.strip()
    if not branch:
        return "", "Detached HEAD or unknown branch."
    return branch, ""


def get_branch_remote(path: Path, branch: str) -> str:
    result = run_git(path, "config", f"branch.{branch}.remote", capture=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def classify_pull_error(stdout: str, stderr: str, remote: str, branch: str) -> tuple[str, str]:
    message = best_git_message(stdout, stderr)
    combined = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
    lowered = combined.lower()

    if "no such remote" in lowered:
        return f"Remote '{remote}' is not configured in this repository.", message

    if (
        "authentication failed" in lowered
        or "permission denied" in lowered
        or "access denied" in lowered
        or "could not read from remote repository" in lowered
        or "repository not found" in lowered
        or "http 401" in lowered
        or "http 403" in lowered
    ):
        return f"Access or authentication failed while pulling {remote}/{branch}.", message

    if (
        "could not resolve host" in lowered
        or "network is unreachable" in lowered
        or "failed to connect" in lowered
        or "connection timed out" in lowered
        or "name or service not known" in lowered
        or "temporary failure in name resolution" in lowered
    ):
        return f"Network/connectivity issue while reaching remote '{remote}'.", message

    if "couldn't find remote ref" in lowered or "remote ref does not exist" in lowered:
        return f"Remote branch {remote}/{branch} does not exist.", message

    if "not possible to fast-forward" in lowered:
        return "Cannot fast-forward. Local and remote branches have diverged.", message

    if "your local changes to the following files would be overwritten" in lowered:
        return "Local uncommitted changes would be overwritten by pull.", message

    if message:
        return f"Pull failed: {message}", message
    return "Pull failed with unknown git error.", ""


def collect_folders(root: Path, recurse: bool, include_root: bool) -> list[Path]:
    folders: list[Path] = []

    if include_root:
        folders.append(root)

    if recurse:
        folders.extend([p for p in root.rglob("*") if p.is_dir()])
    else:
        folders.extend([p for p in root.iterdir() if p.is_dir()])

    return folders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull latest changes for all Git repositories under a root folder."
    )
    parser.add_argument(
        "root_path",
        nargs="?",
        default=".",
        help="Root folder containing many repository folders.",
    )
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Scan repositories recursively under the root folder.",
    )
    parser.add_argument(
        "--include-root",
        action="store_true",
        help="Also treat the root folder itself as a candidate repository.",
    )
    return parser.parse_args()


def main() -> int:
    if shutil.which("git") is None:
        print("ERROR: Git is not installed or not available in PATH.", file=sys.stderr)
        return 1

    args = parse_args()
    root = Path(args.root_path).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"ERROR: Root folder does not exist: {root}", file=sys.stderr)
        return 1

    folders = collect_folders(root, recurse=args.recurse, include_root=args.include_root)
    if not folders:
        print(f"WARNING: No folders found under {root}")
        return 0

    scanned = len(folders)
    repositories = 0
    pulled = 0
    skipped = 0
    non_git = 0
    failed = 0

    print(f"Root folder: {root}")
    print(f"Folders to scan: {scanned}")

    for index, folder in enumerate(folders, start=1):
        print(f"\n[SCAN {index}/{scanned}] {folder}")

        is_repo, repo_reason = get_repo_status(folder)
        if not is_repo:
            print(f"SKIP: {repo_reason}")
            non_git += 1
            continue

        repositories += 1
        print("Repository detected.")

        branch, branch_error = get_current_branch(folder)
        if not branch:
            print(f"SKIP: {branch_error}")
            skipped += 1
            continue

        print(f"Current branch: {branch}")

        remote = get_branch_remote(folder, branch) or "origin"
        print(f"Pull target: {remote}/{branch}")

        pull_result = run_git(folder, "pull", "--ff-only", remote, branch, capture=True)

        if pull_result.returncode == 0:
            print("Pull succeeded.")
            pull_message = best_git_message(pull_result.stdout, pull_result.stderr)
            if pull_message:
                print(f"Git says: {pull_message}")
            pulled += 1
        else:
            reason, git_message = classify_pull_error(
                pull_result.stdout,
                pull_result.stderr,
                remote,
                branch,
            )
            print(f"ERROR: {reason}", file=sys.stderr)
            if git_message:
                print(f"Git says: {git_message}", file=sys.stderr)
            failed += 1

    if repositories == 0:
        print(f"WARNING: No Git repositories found under {root}")

    print("\nSummary")
    print(f"Scanned folders : {scanned}")
    print(f"Git repos found : {repositories}")
    print(f"Non-git folders : {non_git}")
    print(f"Pulled          : {pulled}")
    print(f"Skipped         : {skipped}")
    print(f"Failed          : {failed}")

    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())