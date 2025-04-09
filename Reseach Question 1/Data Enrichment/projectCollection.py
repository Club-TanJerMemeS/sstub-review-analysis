import os
import pandas as pd
import subprocess
from tqdm import tqdm

CSV_PATH = "./MSR Project/TopJavaMavenProjects.csv"
CLONE_DIR = "C:/r"

projects = pd.read_csv(CSV_PATH)
projects['repo'] = projects['repository_url'].str.replace("https://github.com/", "", regex=False)

# test variable to make sure projects cloned are full 
TOP_N = len(projects)
os.makedirs(CLONE_DIR, exist_ok=True)

# actaulyl clone the project
for _, row in tqdm(projects.head(TOP_N).iterrows(), total=TOP_N, desc="Cloning Repos"):
    repo = row['repo']
    owner, name = repo.split("/")
    clone_path = os.path.join(CLONE_DIR, f"{owner}_{name}")

    repo_url = f"https://github.com/{repo}.git"
    print(f"Cloning {repo_url} into {clone_path}")
    subprocess.run(["git", "clone", repo_url, clone_path])
