import os
import json
import subprocess
from tqdm import tqdm
from collections import defaultdict

BUGS_JSON = "./MSR Project/bugs.json"
REPO_DIR = "C:/r"
OUTPUT_FILE = "introducing_commits.jsonl"

#collect bugs from bugs.json 
with open(BUGS_JSON, encoding="utf-8") as f:
    bugs = json.load(f)

#group bugs by project
grouped = defaultdict(list)
for bug in bugs:
    grouped[bug["projectName"]].append(bug)

with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
    for project, project_bugs in tqdm(grouped.items(), desc="Processing Projects"):
        local_repo = os.path.join(REPO_DIR, project.replace(".", "_"))
        if not os.path.exists(local_repo):
            continue

        os.chdir(local_repo)

        #clean to prevent checkout errors (can break so just preventative )
        subprocess.run(["git", "reset", "--hard"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "clean", "-fd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for bug in project_bugs:
            fix_sha = bug["fixCommitSHA1"]
            fix_parent = bug["fixCommitParentSHA1"]
            file_path = bug["bugFilePath"]
            line_num = bug["bugLineNum"]

            try:
                #if file doesnt exist in parent (ie, they removed the file prior then we have to ignore it, only using SZZ not a different version)
                check_file = subprocess.run(
                    ["git", "ls-tree", "-r", fix_parent, "--", file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                if not check_file.stdout:
                    continue

                
                try:
                    file_contents = subprocess.check_output(
                        ["git", "show", f"{fix_parent}:{file_path}"],
                        stderr=subprocess.DEVNULL
                    )
                    total_lines = len(file_contents.decode("utf-8", errors="ignore").splitlines())
                    if line_num > total_lines or line_num <= 0:
                        continue
                except subprocess.CalledProcessError:
                    continue

                # Checkout the parent of the fix commit
                subprocess.run(["git", "checkout", "--detach", fix_parent], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                #git blame the buggy line
                blame_cmd = ["git", "blame", "-L", f"{line_num},{line_num}", file_path]
                result = subprocess.check_output(blame_cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
                introducing_sha = result.split()[0]

                #save results 
                entry = {
                    "projectName": project,
                    "fixCommitSHA1": fix_sha,
                    "fixCommitParentSHA1": fix_parent,
                    "bugFilePath": file_path,
                    "bugLineNum": line_num,
                    "introducingCommitSHA": introducing_sha
                }
                out_f.write(json.dumps(entry) + "\n")

            except Exception as e:
                print(f"[ERROR] {project} - {fix_sha} @ {file_path}:{line_num} → {e}")
