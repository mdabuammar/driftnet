import pandas as pd

df = pd.read_csv('d:/1. Semester 12/Capstone 3/deployment/sample_main/Detailed_Sample_Accuracy.csv')
filtered_df = df[(df['True_Stage'] == 'Stage III') & (df['Predicted_Stage'] == 'Stage III')]

if len(filtered_df) >= 10:
    samples = filtered_df.sample(10)['methylation_sample_id'].values
else:
    samples = filtered_df['methylation_sample_id'].values

print("Here are the samples:")
for s in samples:
    print(s)
