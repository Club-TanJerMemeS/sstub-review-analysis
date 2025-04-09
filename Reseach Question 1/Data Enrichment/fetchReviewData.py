import json
import requests
from GH_token import GITHUB_TOKEN
from tqdm import tqdm

INPUT_FILE = "./MSR Project/introducing_commits.jsonl"
OUTPUT_FILE = "./MSR Project/introducing_commits_enriched.jsonl"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def get_pr_info(owner, repo, commit_sha):
    # check if apart of PR
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/pulls"
    response = requests.get(url, headers=headers)
    if response.status_code != 200 or not response.json():
        return None

    pr = response.json()[0]
    pr_number = pr["number"]

    #collect reviewer meta data
    review_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    reviews = requests.get(review_url, headers=headers).json()
    reviewer_count = len(set(r["user"]["login"] for r in reviews if "user" in r and r["user"]))

    return {
        "pr_number": pr_number,
        "reviewer_count": reviewer_count,
        "pr_created_at": pr["created_at"],
        "pr_merged_at": pr["merged_at"]
    }

#collect cloned projects
with open(INPUT_FILE, "r") as f_in, open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
    lines = [json.loads(line) for line in f_in]

    for entry in tqdm(lines, desc="Enriching Commits"):
        try:
            owner_repo = entry["projectName"].replace(".", "/")
            owner, repo = owner_repo.split("/")
            sha = entry["introducingCommitSHA"]

            pr_info = get_pr_info(owner, repo, sha)
            entry["introducingCommitHasPR"] = bool(pr_info)
            if pr_info:
                entry["introducingPR"] = pr_info

        except Exception as e:
            entry["introducingCommitHasPR"] = False
            print(f"[ERROR] {entry['projectName']} - {e}")

        f_out.write(json.dumps(entry) + "\n")
