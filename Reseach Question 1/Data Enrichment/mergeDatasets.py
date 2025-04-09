import pandas as pd
import json

with open("./MSR Project/introducing_commits_enriched.jsonl", "r", encoding="utf-8") as f:
    enriched = pd.DataFrame([json.loads(line) for line in f])
    
with open("./MSR Project/sstubs.json", "r", encoding="utf-8") as f:
    sstubs = pd.DataFrame(json.load(f))

#rename for consistency
sstubs = sstubs.rename(columns={
    "bugLineNum": "sstub_bugLineNum",
    "fixCommitSHA1": "fixCommitSHA1",
    "bugFilePath": "bugFilePath",
    "bugType": "bugType"
})

# merge sstubs and bugs 
merged = enriched.merge(sstubs[["fixCommitSHA1", "bugFilePath", "sstub_bugLineNum", "bugType"]], left_on=["fixCommitSHA1", "bugFilePath", "bugLineNum"], right_on=["fixCommitSHA1", "bugFilePath", "sstub_bugLineNum"], how="left")

merged["sstub_introduced"] = merged["bugType"].notnull().astype(int)

#collect reviewer ingo
merged["reviewer_count"] = merged["introducingPR"].apply(
    lambda pr: pr.get("reviewer_count", 0) if isinstance(pr, dict) else 0
)

final_df = merged[["fixCommitSHA1", "introducingCommitSHA", "projectName", "bugFilePath", "bugLineNum", "bugType", "reviewer_count", "introducingCommitHasPR", "sstub_introduced"]]

final_df.to_csv("rq1_dataset.csv", index=False)

