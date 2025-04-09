import json
import os

def is_test_file(file_path):
    path = file_path.lower()
    return any(keyword in path for keyword in ['test', 'tests', 'testing'])

def is_valid_fixing_time(bug):
    time = bug.get("TimeToFixHoursCommit")
    return time is not None and time > 0

# Load the bug dataset
with open('merged_checkpoints.json', 'r') as f:
    bug_data = json.load(f)

# Filter: exclude test files AND invalid fixing times
filtered_bugs = [
    bug for bug in bug_data
    if not is_test_file(bug.get("bugFilePath", "")) and is_valid_fixing_time(bug)
]

# Save filtered dataset
with open('bugs_no_test_files.json', 'w') as f:
    json.dump(filtered_bugs, f, indent=4)

print(f"Filtered dataset written with {len(filtered_bugs)} entries (excluding test files and non-positive fixing times).")
print("Saved to:", os.path.abspath('bugs_no_test_files.json'))
