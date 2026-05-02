import pandas as pd

df = pd.read_excel('sample_main/Detailed_Sample_Accuracy.xlsx')
print(df.columns)
for sample in ['sample1727', 'sample2526', 'sample7036']:
    row = df[df['methylation_sample_id'] == sample]
    if not row.empty:
        try:
            print(f"{sample} -> True Level: {row.iloc[0]['stage_clean']}, Predicted: {row.iloc[0]['Predicted Levels']}")
        except:
            print(f"{sample} -> DataFrame row: {row.to_dict()}")
