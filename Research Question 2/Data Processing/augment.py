#!/usr/bin/env python3
import json
import os
import subprocess
import shutil
import stat
from datetime import datetime
from collections import OrderedDict
from github import Github
from tqdm import tqdm
from dotenv import load_dotenv
import diskcache as dc

# -------------------------------
# LOAD ENVIRONMENT VARIABLES
# -------------------------------
load_dotenv()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in environment (.env)")

# Initialize global GitHub API client.
g = Github(GITHUB_TOKEN)

# -------------------------------
# CONFIGURATION
# -------------------------------
SSTUBS_JSON_PATH = os.path.join(os.getcwd(), "sstubs.json")
CHECKPOINT_DIR = os.path.join(os.getcwd(), "augmented_subfiles")
if not os.path.exists(CHECKPOINT_DIR):
    os.makedirs(CHECKPOINT_DIR)

BUG_KEYWORDS = [
    "bug", "bugfix", "bug fix", "bug-fix", "bugfixes",
    "fix", "fixes", "fixed", "patch", "correction", "repair",
    "typo", "error", "exception", "fail", "failure", "crash",
    "issue", "defect", "fault", "problem", "flaw", "mistake",
    "logic error", "inconsistency", "unexpected behavior",
    "misconfiguration", "misuse", "illegal", "unhandled",
    "wrong", "missing", "incorrect", "unexpected",
    "update required", "glitch", "anomaly", "malfunction", 
    "vulnerability", "misimplemented", "misimplementation"
]

LOCAL_CLONES_DIR = os.path.join(os.getcwd(), "clones")
CONTEXT_LINES = 3  # Number of context lines to extract
CHUNK_SIZE = 100   # Number of records per checkpoint

# -------------------------------
# PERSISTENT CACHING USING DISKCACHE
# -------------------------------
commit_cache = dc.Cache('commit_cache')
pr_cache = dc.Cache('pr_cache')

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def parse_owner_repo(project_name: str) -> str:
    """Converts 'Owner.Repo' to 'Owner/Repo'."""
    parts = project_name.split(".")
    if len(parts) == 2:
        owner, repo = parts
        return f"{owner}/{repo}"
    return project_name

def get_repo_url(project_name: str) -> str:
    """Constructs the GitHub repository URL."""
    repo_full = parse_owner_repo(project_name)
    return f"https://github.com/{repo_full}.git"

def get_local_repo_path(project_name: str) -> str:
    """Returns the expected local clone path (e.g., clones/Owner_Repo)."""
    repo_full = parse_owner_repo(project_name)
    local_repo_name = repo_full.replace("/", "_")
    return os.path.join(LOCAL_CLONES_DIR, local_repo_name)

def clean_snippet(snippet: str) -> str:
    """Cleans the snippet by removing escape characters and extra whitespace."""
    return snippet.replace('\\"', '"').strip()

def extract_context_snippet(local_repo_path: str, bug_file_path: str, bug_line_num: int, context: int = CONTEXT_LINES) -> str:
    """Extracts a snippet of context from a file, or returns an empty string if not found."""
    full_file_path = os.path.join(local_repo_path, bug_file_path)
    if not os.path.exists(full_file_path):
        print(f"[WARN] File not found: {full_file_path}. Falling back to sourceBeforeFix.")
        return ""
    try:
        with open(full_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        start = max(0, bug_line_num - context - 1)  # Adjust for 0-indexing
        end = min(len(lines), bug_line_num + context)
        snippet = "".join(lines[start:end]).strip()
        return snippet
    except Exception as e:
        print(f"[ERROR] Failed to extract snippet from {full_file_path}: {e}")
        return ""

def build_enhanced_query(entry: dict, local_repo_path: str) -> str:
    """Constructs an enhanced query using file context or falling back to sourceBeforeFix."""
    source_before = entry.get("sourceBeforeFix", "").strip()
    bug_line_num = entry.get("bugLineNum")
    bug_file_path = entry.get("bugFilePath")
    context_snippet = extract_context_snippet(local_repo_path, bug_file_path, bug_line_num)
    return f'"{context_snippet}"' if context_snippet else f'"{source_before}"'

def get_commit_date(commit_obj):
    """Returns the commit's date using author or committer information."""
    commit_data = commit_obj.commit
    if commit_data.author and commit_data.author.date:
        return commit_data.author.date
    elif commit_data.committer and commit_data.committer.date:
        return commit_data.committer.date
    else:
        return None

def detect_explicit_mention(text: str) -> bool:
    """Returns True if any of the BUG_KEYWORDS appear in the provided text."""
    lower_text = text.lower()
    for kw in BUG_KEYWORDS:
        if kw in lower_text:
            return True
    return False

def find_bug_introducing_commit_local(local_repo_path: str, bug_file_path: str, entry: dict, before_time: str = None) -> (str, str):
    """
    Uses git log with -S and the enhanced query to search for the introducing commit.
    If before_time is provided, adds a '--before' filter.
    Returns (introducing_commit_hash, introducing_commit_date_str) or (None, None).
    """
    query_snippet = build_enhanced_query(entry, local_repo_path)
    cmd = ["git", "log", "-S", query_snippet, "--reverse", "--pretty=format:%H %aI"]
    if before_time:
        cmd.extend(["--before", before_time])
    cmd.extend(["--", bug_file_path])
    try:
        result = subprocess.run(cmd, cwd=local_repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        output = result.stdout.strip()
        if not output:
            return None, None
        first_line = output.split("\n")[0]
        parts = first_line.split(" ", 1)
        return (parts[0], parts[1]) if len(parts) == 2 else (None, None)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] git log failed in {local_repo_path}: {e.stderr}")
        return None, None

def szz_detect_bug_introducing_commit(local_repo_path: str, bug_file_path: str, fix_parent_sha: str, bug_line_num: int) -> (str, str):
    """A simple SZZ implementation using git blame to find the last commit touching the bug line."""
    cmd = ["git", "blame", fix_parent_sha, "--", bug_file_path]
    try:
        result = subprocess.run(
            cmd,
            cwd=local_repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",  # Replace problematic characters
            check=True
        )
        lines = result.stdout.splitlines()
        if len(lines) < bug_line_num:
            return None, None
        target_line = lines[bug_line_num - 1]  # 1-indexed.
        parts = target_line.split()
        if parts:
            introducing_commit_hash = parts[0]
            cmd_date = ["git", "show", "-s", "--format=%aI", introducing_commit_hash]
            result_date = subprocess.run(
                cmd_date,
                cwd=local_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",  # Replace problematic characters
                check=True
            )
            introducing_commit_date = result_date.stdout.strip()
            return introducing_commit_hash, introducing_commit_date
        return None, None
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] git blame failed in {local_repo_path}: {e.stderr}")
        return None, None

def get_pr_info_from_commit(repo_obj, commit_obj):
    """
    Retrieves PR info associated with a commit using the GitHub API.
    Returns (dictionary with PR info, PR object or None).
    """
    pr_info = {}
    try:
        prs = commit_obj.get_pulls()
        for pr in prs:
            full_pr = repo_obj.get_pull(pr.number)
            pr_info = {
                "pr_number": full_pr.number,
                "pr_created_at": full_pr.created_at.isoformat() if full_pr.created_at else None,
                "pr_merged_at": full_pr.merged_at.isoformat() if full_pr.merged_at else None,
                "reviewer_count": len({rv.user.login for rv in full_pr.get_reviews() if rv.user}),
            }
            return pr_info, full_pr
    except Exception as e:
        print(f"[ERROR] Getting PR info failed: {e}")
    return pr_info, None

def handle_remove_readonly(func, path, exc_info):
    """Callback for shutil.rmtree to handle read-only files on Windows."""
    import errno
    exc_value = exc_info[1]
    if func in (os.rmdir, os.remove, os.unlink) and exc_value.errno == errno.EACCES:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

# -------------------------------
# PERSISTENT CACHING FUNCTIONS
# -------------------------------
def get_cached_commit(repo_obj, commit_sha: str):
    if commit_sha in commit_cache:
        return commit_cache[commit_sha]
    try:
        commit_obj = repo_obj.get_commit(sha=commit_sha)
        commit_cache[commit_sha] = commit_obj
        return commit_obj
    except Exception as e:
        print(f"[ERROR] Failed to fetch commit {commit_sha}: {e}")
        return None

def get_cached_pr_info(repo_obj, commit_sha: str):
    if commit_sha in pr_cache:
        return pr_cache[commit_sha]
    commit_obj = get_cached_commit(repo_obj, commit_sha)
    if commit_obj is None:
        return {}, None
    pr_info, pr_obj = get_pr_info_from_commit(repo_obj, commit_obj)
    pr_cache[commit_sha] = (pr_info, pr_obj)
    return pr_info, pr_obj

# -------------------------------
# PROCESSING FUNCTION FOR A SINGLE ENTRY
# -------------------------------
def process_entry_inner(entry, local_repo_path, repo_obj):
    fix_sha = entry.get("fixCommitSHA1")
    bug_type = entry.get("bugType")
    source_before_fix = entry.get("sourceBeforeFix")
    bug_file_path = entry.get("bugFilePath")
    bug_line_num = entry.get("bugLineNum")
    fix_parent_sha = entry.get("fixCommitParentSHA1")
    
    fix_commit_obj = get_cached_commit(repo_obj, fix_sha)
    if not fix_commit_obj:
        return None
    fix_commit_date = get_commit_date(fix_commit_obj)
    fix_commit_date_str = fix_commit_date.isoformat() if fix_commit_date else None
    fix_pr_info, _ = get_cached_pr_info(repo_obj, fix_sha)
    fix_commit_has_pr = bool(fix_pr_info)
    
    cutoff_time = fix_pr_info.get("pr_merged_at") if fix_pr_info.get("pr_merged_at") else fix_commit_date_str
    
    if fix_parent_sha:
        intro_commit_hash, intro_commit_date_str = szz_detect_bug_introducing_commit(local_repo_path, bug_file_path, fix_parent_sha, bug_line_num)
    else:
        intro_commit_hash, intro_commit_date_str = find_bug_introducing_commit_local(local_repo_path, bug_file_path, entry, before_time=cutoff_time)
    
    if intro_commit_hash:
        print(f"[INFO] Found introducing commit {intro_commit_hash} with date {intro_commit_date_str}")
    else:
        print(f"[WARN] No introducing commit found for snippet: {source_before_fix}")
    
    time_to_fix_hours_commit = None
    if fix_commit_date_str and intro_commit_date_str:
        try:
            fix_dt = datetime.fromisoformat(fix_commit_date_str)
            intro_dt = datetime.fromisoformat(intro_commit_date_str)
            delta = fix_dt - intro_dt
            time_to_fix_hours_commit = delta.total_seconds() / 3600.0
        except Exception as e:
            print(f"[ERROR] Commit-based time-to-fix calculation failed: {e}")
    
    introducing_commit_has_pr = False
    introducing_pr_info = {}
    if intro_commit_hash:
        try:
            intro_commit_obj = get_cached_commit(repo_obj, intro_commit_hash)
            introducing_pr_info, _ = get_cached_pr_info(repo_obj, intro_commit_hash)
            introducing_commit_has_pr = bool(introducing_pr_info)
        except Exception as e:
            print(f"[ERROR] Failed to get PR info for introducing commit {intro_commit_hash}: {e}")
    
    time_to_fix_hours_pr = None
    fix_pr_merged = fix_pr_info.get("pr_merged_at") if fix_pr_info.get("pr_merged_at") else None
    intro_pr_merged = introducing_pr_info.get("pr_merged_at") if introducing_pr_info.get("pr_merged_at") else None
    if fix_pr_merged and intro_pr_merged:
        try:
            fix_pr_merge_dt = datetime.fromisoformat(fix_pr_merged)
            intro_pr_merge_dt = datetime.fromisoformat(intro_pr_merged)
            delta_pr = fix_pr_merge_dt - intro_pr_merge_dt
            time_to_fix_hours_pr = delta_pr.total_seconds() / 3600.0
        except Exception as e:
            print(f"[ERROR] PR-based time-to-fix calculation failed: {e}")
    
    # Separate explicit mention detection:
    explicit_bug_mention_commit = False
    explicit_bug_mention_pr = False
    if intro_commit_hash:
        try:
            intro_commit_obj = get_cached_commit(repo_obj, intro_commit_hash)
            commit_message = intro_commit_obj.commit.message
            if detect_explicit_mention(commit_message):
                explicit_bug_mention_commit = True
                print(f"[DEBUG] Found explicit mention in introducing commit message: {commit_message}")
        except Exception as e:
            print(f"[ERROR] Failed to get commit message for introducing commit {intro_commit_hash}: {e}")
        
        if introducing_pr_info:
            try:
                _, intro_pr_obj = get_cached_pr_info(repo_obj, intro_commit_hash)
                if intro_pr_obj:
                    for comment in intro_pr_obj.get_review_comments():
                        if detect_explicit_mention(comment.body):
                            explicit_bug_mention_pr = True
                            print(f"[DEBUG] Found explicit mention in introducing PR review comment: {comment.body}")
                            break
            except Exception as e:
                print(f"[ERROR] Failed to get review comments for introducing PR: {e}")
    
    record = OrderedDict()
    record["fixCommitSHA1"] = fix_sha
    record["fixCommitDate"] = fix_commit_date_str
    record["fixCommitHasPR"] = fix_commit_has_pr
    record["fixPR"] = fix_pr_info
    record["introducingCommitSHA"] = intro_commit_hash
    record["introducingCommitDate"] = intro_commit_date_str
    record["introducingCommitHasPR"] = introducing_commit_has_pr
    record["introducingPR"] = introducing_pr_info
    record["TimeToFixHoursCommit"] = time_to_fix_hours_commit
    record["TimeToFixHoursPR"] = time_to_fix_hours_pr
    record["explicitMentionInIntroducingCommit"] = explicit_bug_mention_commit
    record["explicitMentionInIntroducingPR"] = explicit_bug_mention_pr
    record["bugType"] = bug_type
    record["projectName"] = entry.get("projectName")
    record["sourceBeforeFix"] = source_before_fix
    record["bugFilePath"] = bug_file_path
    record["bugLineNum"] = bug_line_num
    return record

def process_repo_entries(repo_full_name, entries, global_pbar):
    results = []
    local_repo_path = get_local_repo_path(repo_full_name)
    if not os.path.exists(local_repo_path):
        repo_url = get_repo_url(repo_full_name)
        print(f"[INFO] Cloning {repo_url} into {local_repo_path}")
        try:
            subprocess.run(["git", "clone", "--config", "core.longpaths=true", repo_url, local_repo_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to clone {repo_url}: {e.stderr}")
            return results
    try:
        repo_obj = g.get_repo(repo_full_name)
    except Exception as e:
        print(f"[ERROR] Cannot access repository {repo_full_name}: {e}")
        return results

    for entry in entries:
        record = process_entry_inner(entry, local_repo_path, repo_obj)
        global_pbar.update(1)
        if record:
            results.append(record)
    print(f"[INFO] Deleting local clone for {repo_full_name} at {local_repo_path}")
    shutil.rmtree(local_repo_path, onerror=handle_remove_readonly)
    return results

def main():
    # Load the full JSON dataset.
    with open(SSTUBS_JSON_PATH, "r", encoding="utf-8") as f:
        sstubs_data = json.load(f)
    
    total_entries = len(sstubs_data)
    global_pbar = tqdm(total=total_entries, desc="Processing SStuBs", unit="stub")
    
    augmented_records = []
    # Process records in chunks of CHUNK_SIZE.
    for i in range(0, total_entries, CHUNK_SIZE):
        checkpoint_file = os.path.join(CHECKPOINT_DIR, f"checkpoint_{i}.json")
        if os.path.exists(checkpoint_file):
            print(f"[INFO] Skipping checkpoint {i} as it already exists.")
            global_pbar.update(CHUNK_SIZE)
            continue
        
        chunk = sstubs_data[i:i+CHUNK_SIZE]
        current_repo = None
        current_local_repo_path = None
        chunk_records = []
        for entry in chunk:
            fix_sha = entry.get("fixCommitSHA1")
            project_name = entry.get("projectName")
            source_before_fix = entry.get("sourceBeforeFix")
            bug_file_path = entry.get("bugFilePath")
            bug_line_num = entry.get("bugLineNum")
            fix_parent_sha = entry.get("fixCommitParentSHA1")
            bug_type = entry.get("bugType")
        
            if not fix_sha or not project_name or not source_before_fix or not bug_file_path or not bug_line_num:
                print("[WARN] Missing essential fields; skipping record.")
                global_pbar.update(1)
                continue
        
            repo_full_name = parse_owner_repo(project_name)
            new_local_repo_path = get_local_repo_path(project_name)
        
            if current_repo != repo_full_name:
                if current_local_repo_path and os.path.exists(current_local_repo_path):
                    print(f"[INFO] Deleting local clone for {current_repo} at {current_local_repo_path}")
                    shutil.rmtree(current_local_repo_path, onerror=handle_remove_readonly)
                if not os.path.exists(new_local_repo_path):
                    repo_url = get_repo_url(project_name)
                    print(f"[INFO] Cloning {repo_url} into {new_local_repo_path}")
                    try:
                        subprocess.run(["git", "clone", "--config", "core.longpaths=true", repo_url, new_local_repo_path], check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"[ERROR] Failed to clone {repo_url}: {e.stderr}")
                        global_pbar.update(1)
                        continue
                current_repo = repo_full_name
                current_local_repo_path = new_local_repo_path
        
            print(f"\n[INFO] Processing project: {repo_full_name}, fix commit: {fix_sha}")
        
            try:
                repo_obj = g.get_repo(repo_full_name)
            except Exception as e:
                print(f"[ERROR] Cannot access repository {repo_full_name}: {e}")
                global_pbar.update(1)
                continue
            try:
                fix_commit_obj = repo_obj.get_commit(sha=fix_sha)
                fix_commit_date = get_commit_date(fix_commit_obj)
            except Exception as e:
                print(f"[ERROR] Cannot find fix commit {fix_sha}: {e}")
                global_pbar.update(1)
                continue
            fix_commit_date_str = fix_commit_date.isoformat() if fix_commit_date else None
            fix_pr_info, _ = get_pr_info_from_commit(repo_obj, fix_commit_obj)
        
            cutoff_time = fix_pr_info.get("pr_merged_at") if fix_pr_info.get("pr_merged_at") else fix_commit_date_str
        
            if fix_parent_sha:
                intro_commit_hash, intro_commit_date_str = szz_detect_bug_introducing_commit(
                    current_local_repo_path, bug_file_path, fix_parent_sha, bug_line_num
                )
            else:
                intro_commit_hash, intro_commit_date_str = find_bug_introducing_commit_local(
                    current_local_repo_path, bug_file_path, entry, before_time=cutoff_time
                )
        
            if intro_commit_hash:
                print(f"[INFO] Found introducing commit {intro_commit_hash} with date {intro_commit_date_str}")
            else:
                print(f"[WARN] No introducing commit found for snippet: {source_before_fix}")
        
            time_to_fix_hours_commit = None
            if fix_commit_date_str and intro_commit_date_str:
                try:
                    fix_dt = datetime.fromisoformat(fix_commit_date_str)
                    intro_dt = datetime.fromisoformat(intro_commit_date_str)
                    delta = fix_dt - intro_dt
                    time_to_fix_hours_commit = delta.total_seconds() / 3600.0
                except Exception as e:
                    print(f"[ERROR] Commit-based time-to-fix calculation failed: {e}")
        
            introducing_commit_has_pr = False
            introducing_pr_info = {}
            if intro_commit_hash:
                try:
                    intro_commit_obj = repo_obj.get_commit(sha=intro_commit_hash)
                    introducing_pr_info, _ = get_pr_info_from_commit(repo_obj, intro_commit_obj)
                    introducing_commit_has_pr = bool(introducing_pr_info)
                except Exception as e:
                    print(f"[ERROR] Failed to get PR info for introducing commit {intro_commit_hash}: {e}")
        
            time_to_fix_hours_pr = None
            fix_pr_merged = fix_pr_info.get("pr_merged_at") if fix_pr_info.get("pr_merged_at") else None
            intro_pr_merged = introducing_pr_info.get("pr_merged_at") if introducing_pr_info.get("pr_merged_at") else None
            if fix_pr_merged and intro_pr_merged:
                try:
                    fix_pr_merge_dt = datetime.fromisoformat(fix_pr_merged)
                    intro_pr_merge_dt = datetime.fromisoformat(intro_pr_merged)
                    delta_pr = fix_pr_merge_dt - intro_pr_merge_dt
                    time_to_fix_hours_pr = delta_pr.total_seconds() / 3600.0
                except Exception as e:
                    print(f"[ERROR] PR-based time-to-fix calculation failed: {e}")
        
            explicit_bug_mention_commit = False
            explicit_bug_mention_pr = False
            if intro_commit_hash:
                try:
                    intro_commit_obj = repo_obj.get_commit(sha=intro_commit_hash)
                    commit_message = intro_commit_obj.commit.message
                    if detect_explicit_mention(commit_message):
                        explicit_bug_mention_commit = True
                        print(f"[DEBUG] Found explicit mention in introducing commit message: {commit_message}")
                except Exception as e:
                    print(f"[ERROR] Failed to get commit message for introducing commit {intro_commit_hash}: {e}")
        
            if introducing_pr_info:
                try:
                    _, intro_pr_obj = get_pr_info_from_commit(repo_obj, intro_commit_obj)
                    if intro_pr_obj:
                        for comment in intro_pr_obj.get_review_comments():
                            if detect_explicit_mention(comment.body):
                                explicit_bug_mention_pr = True
                                print(f"[DEBUG] Found explicit mention in introducing PR review comment: {comment.body}")
                                break
                except Exception as e:
                    print(f"[ERROR] Failed to get review comments for introducing PR: {e}")
        
            record = OrderedDict()
            record["fixCommitSHA1"] = fix_sha
            record["fixCommitDate"] = fix_commit_date_str
            record["fixCommitHasPR"] = bool(fix_pr_info)
            record["fixPR"] = fix_pr_info
            record["introducingCommitSHA"] = intro_commit_hash
            record["introducingCommitDate"] = intro_commit_date_str
            record["introducingCommitHasPR"] = bool(introducing_pr_info)
            record["introducingPR"] = introducing_pr_info
            record["TimeToFixHoursCommit"] = time_to_fix_hours_commit
            record["TimeToFixHoursPR"] = time_to_fix_hours_pr
            record["explicitMentionInIntroducingCommit"] = explicit_bug_mention_commit
            record["explicitMentionInIntroducingPR"] = explicit_bug_mention_pr
            record["bugType"] = bug_type
            record["projectName"] = project_name
            record["sourceBeforeFix"] = source_before_fix
            record["bugFilePath"] = bug_file_path
            record["bugLineNum"] = bug_line_num
        
            augmented_records.append(record)
        
        # End of chunk: save this chunk's results as a checkpoint.
        checkpoint_file = os.path.join(CHECKPOINT_DIR, f"checkpoint_{i}.json")
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(augmented_records, f, indent=2, default=str)
        print(f"[INFO] Saved checkpoint for records {i} to {i+len(augmented_records)} in {checkpoint_file}")
        augmented_records = []  # Reset for next chunk
    
    global_pbar.close()
    print(f"\n[INFO] Augmentation complete for {total_entries} records.")

if __name__ == "__main__":
    main()
