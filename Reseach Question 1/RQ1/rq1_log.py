import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import OneHotEncoder
import matplotlib.pyplot as plt

df = pd.read_csv("./MSR Project/rq1_dataset.csv")

# Remove the bugs that dont have an associated PR with it
df = df[df["introducingCommitHasPR"] == True]

# take only bugs that are sstubs
sstub_only = df[df["sstub_introduced"] == 1]

#need to remove any sstubs that are considered tests (removing all that are under a test directory) 
sstub_only = sstub_only[~sstub_only["bugFilePath"].str.contains("/test/", case=False, na=False)]

# removing sstubs that have invalid bug type or reviewwer count 
sstub_only = sstub_only.dropna(subset=["bugType", "reviewer_count"])


X = sstub_only[["reviewer_count"]]
y = sstub_only["bugType"]

#one hot encode teh bug types
encoder = OneHotEncoder(drop="first", sparse=False)
y_encoded = encoder.fit_transform(y.values.reshape(-1, 1))
y_cols = encoder.get_feature_names_out(["bugType"])

#test train 80/20 split
X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2)

model = OneVsRestClassifier(LogisticRegression(max_iter=1000))
model.fit(X_train, y_train)

#predict One Vs All classifications label
y_pred = model.predict(X_test)

#collect coefficient for each bug type
coef_data = []
for i, bug in enumerate(y_cols):
    coef = model.estimators_[i].coef_[0][0]
    coef_data.append((bug, coef))
    print(f"{bug}: coefficient = {coef:.4f}")

#plot
coef_df = pd.DataFrame(coef_data, columns=["bugType", "coefficient"])
coef_df = coef_df.sort_values(by="coefficient", ascending=False)
plt.figure(figsize=(12, 6))
plt.bar(coef_df["bugType"], coef_df["coefficient"])
plt.axhline(0, color='gray', linestyle='--')
plt.xticks(rotation=90)
plt.ylabel("Reviewer Count Coefficient")
plt.title("Reviewer Count Influence on Each SStuB Type")
plt.tight_layout()
plt.show()
