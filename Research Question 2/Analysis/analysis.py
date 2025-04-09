import json
import statistics
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines import CoxPHFitter
from collections import defaultdict
import numpy as np


# Load the merged JSON file
merged_file_path = "bugs_no_test_files.json"

with open(merged_file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Step 1: Display the total number of JSON objects
total_objects = len(data)

# Step 2: Filter out bug files that DO NOT have 'test' in the path
def is_not_test_file(file_path):
    return 'test' not in file_path.lower()

non_test_file_objects = [item for item in data if is_not_test_file(item.get("bugFilePath", ""))]

# Step 3: Filter and keep only ones with non-empty PR fields (from non-test files)
pr_filtered_objects = [
    item for item in non_test_file_objects
    if item.get("fixPR") and item["fixPR"].get("pr_merged_at") is not None
    and item.get("introducingPR") and item["introducingPR"].get("pr_merged_at") is not None
]

# Step 4: Objects with explicit mentions (in PR or commit) in step 3
explicit_mention_objects = [
    item for item in pr_filtered_objects 
    if item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR")
]

# Step 5: Average fixing time of PR-filtered entries WITH explicit mentions
explicit_fixing_times = [
    item["TimeToFixHoursCommit"] for item in pr_filtered_objects
    if (item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR"))
    and item.get("TimeToFixHoursCommit") is not None
]
avg_fixing_time_explicit = (
    sum(explicit_fixing_times) / len(explicit_fixing_times) if explicit_fixing_times else 0
)

# Step 6: Average fixing time of PR-filtered entries WITHOUT explicit mentions
non_explicit_fixing_times = [
    item["TimeToFixHoursCommit"] for item in pr_filtered_objects
    if not (item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR"))
    and item.get("TimeToFixHoursCommit") is not None
]
avg_fixing_time_non_explicit = (
    sum(non_explicit_fixing_times) / len(non_explicit_fixing_times) if non_explicit_fixing_times else 0
)

# Step 7: Median fixing time of PR-filtered entries WITH explicit mentions
median_fixing_time_explicit = (
    statistics.median(explicit_fixing_times) if explicit_fixing_times else 0
)

# Step 8: Median fixing time of PR-filtered entries WITHOUT explicit mentions
median_fixing_time_non_explicit = (
    statistics.median(non_explicit_fixing_times) if non_explicit_fixing_times else 0
)

print(f"1. Total number of JSON objects: {total_objects}")
print(f"2. Bug objects WITHOUT 'test' in file path: {len(non_test_file_objects)}")
print(f"3. Objects with non-empty PR fields (from non-test files): {len(pr_filtered_objects)}")
print(f"4. Objects with explicit mentions (from step 3): {len(explicit_mention_objects)}")
print(f"5. Average fixing time (explicit mentions): {avg_fixing_time_explicit / 24:.2f} days")
print(f"6. Average fixing time (without explicit mentions): {avg_fixing_time_non_explicit / 24:.2f} days")
print(f"7. Median fixing time (explicit mentions): {median_fixing_time_explicit / 24:.2f} days")
print(f"8. Median fixing time (without explicit mentions): {median_fixing_time_non_explicit / 24:.2f} days")


# Step 9: Prepare bug-type level analysis
grouped_data = {}

for item in pr_filtered_objects:
    bug_type = item.get("bugType", "Unknown")
    mention_group = "With Explicit Mention" if (
        item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR")
    ) else "Without Explicit Mention"
    
    if item.get("TimeToFixHoursCommit") is not None:
        grouped_data.setdefault((bug_type, mention_group), []).append(item["TimeToFixHoursCommit"] / 24)

# Step 10: Construct DataFrame for plotting with only bug types having both groups
bug_type_groups = defaultdict(dict)

for (bug_type, mention_group), values in grouped_data.items():
    bug_type_groups[bug_type][mention_group] = values

# Keep only bug types that have both mention groups
filtered_bug_types = {
    bt: groups for bt, groups in bug_type_groups.items()
    if (
        "With Explicit Mention" in groups and groups["With Explicit Mention"]
        and "Without Explicit Mention" in groups and groups["Without Explicit Mention"]
    )
}

# Build plot_data from filtered bug types
plot_data = []
for bug_type, groups in filtered_bug_types.items():
    for group_name, values in groups.items():
        plot_data.append({
            "Bug Type": bug_type,
            "Group": group_name,
            "Mean Fix Time (days)": sum(values) / len(values),
            "Median Fix Time (days)": statistics.median(values)
        })

# Convert to DataFrame
df = pd.DataFrame(plot_data)

# Reshape data for plotting
mean_df = df.pivot(index="Bug Type", columns="Group", values="Mean Fix Time (days)")
median_df = df.pivot(index="Bug Type", columns="Group", values="Median Fix Time (days)")

# Reshape data for plotting
mean_df = df.pivot(index="Bug Type", columns="Group", values="Mean Fix Time (days)")
median_df = df.pivot(index="Bug Type", columns="Group", values="Median Fix Time (days)")

# Plot Average Fix Time Bar Chart
mean_df.plot(kind="bar", figsize=(14, 6), title="Average Fix Time by Bug Type (Days)")
plt.ylabel("Average Fix Time (Days)")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()

# Plot Median Fix Time Bar Chart
median_df.plot(kind="bar", figsize=(14, 6), title="Median Fix Time by Bug Type (Days)")
plt.ylabel("Median Fix Time (Days)")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()

from lifelines import KaplanMeierFitter
import matplotlib.pyplot as plt

# Prepare data for Kaplan-Meier analysis
kmf = KaplanMeierFitter()

# Create lists to store data
durations = []  # time to fix (in days)
event_observed = []  # True if fixed (all are True in your case since they have TimeToFix)
groups = []  # group label

for item in pr_filtered_objects:
    if item.get("TimeToFixHoursCommit") is None:
        continue
    
    time_to_fix_days = item["TimeToFixHoursCommit"] / 24
    mention_status = (
        "With Explicit Mention" if item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR")
        else "Without Explicit Mention"
    )
    
    durations.append(time_to_fix_days)
    event_observed.append(True)  # since all are fixed
    groups.append(mention_status)

# Plot Kaplan-Meier curves for explicit vs non-explicit mentions
plt.figure(figsize=(10, 6))
for group_name in set(groups):
    mask = [g == group_name for g in groups]
    kmf.fit(durations=[d for d, m in zip(durations, mask) if m],
            event_observed=[e for e, m in zip(event_observed, mask) if m],
            label=group_name)
    kmf.plot_survival_function()

plt.title("Kaplan-Meier Curve: Bug Fix Time by Explicit Mention")
plt.xlabel("Time to Fix (Days)")
plt.ylabel("Survival Probability (Bug Still Not Fixed)")
plt.grid(True)
plt.tight_layout()
plt.show()

# Get all unique bug types
unique_bug_types = sorted(set(item.get("bugType", "Unknown").strip() for item in pr_filtered_objects))
# Collect Cox model results for visualization
cox_results = []

for bug_type in unique_bug_types:
    cox_data = []

    # Collect samples of the current bug type
    for item in pr_filtered_objects:
        if item.get("bugType", "Unknown").strip() != bug_type:
            continue

        time_to_fix = item.get("TimeToFixHoursCommit")
        if time_to_fix is None or time_to_fix <= 0:
            continue

        cox_data.append({
            "time_to_fix": time_to_fix,
            "event_observed": 1,
            "explicit_mention": int(
                item.get("explicitMentionInIntroducingCommit") or item.get("explicitMentionInIntroducingPR")
            )
        })

    # Skip if not enough data or no variation in explicit_mention
    if len(cox_data) < 10 or len(set(row["explicit_mention"] for row in cox_data)) < 2:
        continue

    # Fit the Cox model
    cox_df = pd.DataFrame(cox_data)
    cph = CoxPHFitter()
    cph.fit(cox_df, duration_col="time_to_fix", event_col="event_observed")
    summary = cph.summary.loc["explicit_mention"]

    cox_results.append({
        "Bug Type": bug_type,
        "Hazard Ratio (exp(coef))": summary["exp(coef)"],
        "Lower CI": summary["exp(coef) lower 95%"],
        "Upper CI": summary["exp(coef) upper 95%"],
        "p-value": summary["p"]
    })

# Convert results to DataFrame and sort by hazard ratio
cox_df_viz = pd.DataFrame(cox_results).sort_values(by="Hazard Ratio (exp(coef))", ascending=False)

# Plot as forest plot
plt.figure(figsize=(10, 8))
plt.errorbar(
    x=cox_df_viz["Hazard Ratio (exp(coef))"],
    y=cox_df_viz["Bug Type"],
    xerr=[
        cox_df_viz["Hazard Ratio (exp(coef))"] - cox_df_viz["Lower CI"],
        cox_df_viz["Upper CI"] - cox_df_viz["Hazard Ratio (exp(coef))"]
    ],
    fmt='o', capsize=5, ecolor='gray', color='blue'
)

plt.axvline(x=1, color='red', linestyle='--', label="No Effect (HR=1)")
plt.xlabel("Hazard Ratio")
plt.title("Cox Model: Effect of Explicit Mention on Bug Fix Time by Bug Type")
plt.grid(True, axis='x')
plt.legend()
plt.tight_layout()
plt.show()
