import os
import pandas as pd
import numpy as np

folder = r'd:\1. Semester 12\Capstone 3\deployment\sample_main'

# Read accuracy 
df_acc = pd.read_excel(os.path.join(folder, 'Detailed_Sample_Accuracy.xlsx'))
print('--- Detailed_Sample_Accuracy.xlsx --')
print(df_acc.head(5).to_string())

# Read processed data
df_proc = pd.read_excel(os.path.join(folder, 'Final_Processed_Data_with_MethylationID.xlsx'))
print('\n--- Final_Processed_Data_with_MethylationID.xlsx --')
print(df_proc.columns.tolist()[:10])
print(df_proc.columns.tolist()[-15:])

for s_id in ['sample1727', 'sample2526', 'sample7036']:
    sample = df_proc[df_proc['methylation_sample_id'] == s_id]
    if not sample.empty:
        print(f'\n{s_id} clinical factors:')
        for col in df_proc.columns[-15:]:
            print(f"{col}: {sample[col].values[0]}")
