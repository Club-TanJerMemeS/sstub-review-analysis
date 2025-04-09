import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

df = pd.read_csv("./MSR Project/rq1_dataset.csv")


# Remove the bugs that dont have an associated PR with it
df = df[df["introducingCommitHasPR"] == True]

# take only bugs that are sstubs
sstub_only = df[df["sstub_introduced"] == 1]

#need to remove any sstubs that are considered tests (removing all that are under a test directory) 
sstub_only = sstub_only[~sstub_only["bugFilePath"].str.contains("/test/", case=False, na=False)]

# removing sstubs that have invalid bug type or reviewwer count 
sstub_only = sstub_only.dropna(subset=["bugType", "reviewer_count"])

#bin reviewer counts 0,1,2,3,4+
sstub_only["reviewer_bin"] = pd.cut(
    sstub_only["reviewer_count"],
    bins=[-1, 0, 1, 2, 3, np.inf],
    labels=["0", "1", "2", "3", "4+"]
)

#creat contingency for chi
contingency = pd.crosstab(sstub_only["reviewer_bin"], sstub_only["bugType"])

chi2, p, dof, expected = chi2_contingency(contingency)

print(f"Chi-square statistic: {chi2:.2f}")
print(f"Degrees of freedom: {dof}")
print(f"P-value: {p:.4e}")

#heatmap plot
plt.figure(figsize=(18, 7))
sns.heatmap(
    contingency,
    annot=True,
    fmt="d",
    cmap="Blues",
    norm=LogNorm(),
    cbar_kws={"label": "Count"}
)
plt.title("SStuB Type Distribution by Reviewer Count Bin")
plt.ylabel("Reviewer Count (Binned)")
plt.xlabel("SStuB Type")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
