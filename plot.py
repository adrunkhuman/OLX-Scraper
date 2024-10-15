import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df: pd.DataFrame = pd.read_json("adverts_export.txt", lines=True)
df = df[df["model"] != "Unknown"]
print(df)

# Filter models with n >= 5
model_counts = df["model"].value_counts()
models_with_n_ge_5 = model_counts[model_counts >= 5].index

# Filter the DataFrame to include only those models
df = df[df["model"].isin(models_with_n_ge_5)]

# Filter the data for "Używane"
df_uzywane = df[df["state"] == "Używane"]
df_uzywane = df_uzywane[df_uzywane["price"] < 5000]
df_uzywane = df_uzywane[df_uzywane["price"] > 200]

# Calculate the average price per model to sort the models
model_order = df_uzywane.groupby("model")["price"].mean().sort_values().index

# Create the figure
plt.figure(figsize=(8, 6))

# Plot the boxplot, sorted by average price
sns.boxplot(data=df_uzywane, x="price", y="model", order=model_order)

# Add sample size annotations to the right of each box
for i, model in enumerate(model_order):
    sample_size = len(df_uzywane[df_uzywane["model"] == model])
    mean_price = df_uzywane[df_uzywane["model"] == model]["price"].mean()
    plt.text(5, i, f"n={sample_size}", va="center")

# Set title and labels
plt.title("Price Distribution by GPU Model (Używane)")
plt.xlabel("Price")
plt.ylabel("Model")

# Adjust layout and show the plot
plt.tight_layout()
plt.show()
