import os
import glob
import pandas as pd
import numpy as np

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from app.inference import DriftNetInference

def main():
    folder = r"d:\1. Semester 12\Capstone 3\deployment\sample_main"
    
    print("Loading AI pipeline...")
    inference = DriftNetInference()
    print("Pipeline loaded.\n")
    
    df_proc = pd.read_csv(os.path.join(folder, "Final_Processed_Data_with_MethylationID.csv"))
    
    clinical_expected = [
        "demographic.gender", "demographic.vital_status", "samples.sample_type",
        "cases.disease_type", "samples.tissue_type", "diagnoses.primary_diagnosis",
        "diagnoses.tissue_or_organ_of_origin", "diagnoses.morphology",
        "diagnoses.age_at_diagnosis", "diagnoses.prior_treatment",
        "diagnoses.prior_malignancy", "demographic.race", "demographic.ethnicity"
    ]
    
    txt_files = glob.glob(os.path.join(folder, "*.txt"))
    test_ids = [os.path.splitext(os.path.basename(f))[0] for f in txt_files]

    for s_id in test_ids:
        print("="*60)
        print(f"TESTING TARGET: {s_id}")
        
        row = df_proc[df_proc["methylation_sample_id"] == s_id]
        if row.empty:
            print(f"[!] No metadata found for {s_id}")
            continue
            
        clinical_data = {}
        for col in clinical_expected:
            if col in row.columns:
                clinical_data[col] = str(row[col].values[0])
            else:
                clinical_data[col] = "0"
                
        true_stage = row['stage_clean'].values[0] if 'stage_clean' in row.columns else 'UNKNOWN'
        
        kaggle_latent = []
        for i in range(1, 151):
            col_name = f"latent_{i}"
            if col_name in row.columns:
                kaggle_latent.append(row[col_name].values[0])
                
        meth_file = os.path.join(folder, f"{s_id}.txt")
        print("1. Parsing methylation file locally...")
        meth_raw, raw_cpg_count = inference.parse_methylation_txt(meth_file)
        
        print("2. Cleaning methylation (align/impute/pad)...")
        meth_clean = inference.clean_methylation_array(meth_raw)
        
        print("3. Generating Latent Features using Local PyTorch Model...")
        local_latent = inference.get_latent_features(meth_clean)
        
        print("4. Encoding Clinical Features...")
        encoded_clin = inference.encode_clinical_input(clinical_data)
        
        print("5. Running Contrastive Keras Encoder...")
        contrastive = inference.get_contrastive_embedding(local_latent, encoded_clin)
        
        print("6. DriftNet Classification...")
        pred_dict = inference.predict_stage(contrastive, encoded_clin)
        
        print(f"\n--- RESULTS FOR {s_id} ---")
        print(f"Expected Ground Truth Stage: {true_stage}")
        print(f"DriftNet Local Prediction  : {pred_dict['predicted_stage']} ({pred_dict['confidence']:.4f} probability)")
        print(f"Probabilities              : {pred_dict['probabilities']}")
        
        print("\nLatent Feature Comparison (First 5):")
        if len(kaggle_latent) >= 5:
            print(f"  Kaggle Latent  : {np.array(kaggle_latent[:5])}")
        print(f"  Local Latent   : {local_latent[0][:5]}")
        
        if len(kaggle_latent) == 150:
            mse = np.mean((np.array(kaggle_latent) - local_latent[0])**2)
            print(f"  Overall MSE between Kaggle vs Local Latent Autoencoder: {mse:.7f}")
        else:
            print("  [Could not find Kaggle latents in Excel sheet columns]")
            
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
