import pandas as pd
df = pd.read_csv('d:/1. Semester 12/Capstone 3/deployment/sample_main/Detailed_Sample_Accuracy.csv')
for s in ['sample1002', 'sample1384', 'sample152', 'sample1727', 'sample6788', 'sample6796', 'sample7020']:
    row = df[df['methylation_sample_id'] == s]
    if not row.empty:
        try:
            print(f"{s} -> True: {row.iloc[0]['True_Stage']}, Kaggle Predicted: {row.iloc[0]['Predicted_Stage']}")
        except:
            pass
