import os
import json
import zipfile
import tempfile
import shutil

def remove_quantization_config(obj):
    if isinstance(obj, dict):
        obj.pop('quantization_config', None)
        for key, value in list(obj.items()):
            remove_quantization_config(value)
    elif isinstance(obj, list):
        for item in obj:
            remove_quantization_config(item)

def patch_keras_file(src_path, dst_path):
    print(f"Applying patch to {src_path} -> {dst_path}")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Extract archive
        with zipfile.ZipFile(src_path, 'r') as zf:
            zf.extractall(tmp_dir)
            
        # Patch config.json
        config_path = os.path.join(tmp_dir, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            remove_quantization_config(cfg)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f)
            print("  Stripped quantization_config from config.json")
        else:
            print("  No config.json found!?")

        # Repackage archive
        with zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, tmp_dir)
                    zf.write(file_path, arcname)
    print("  Repackaged successfully.\n")


def main():
    assets = os.path.join(os.path.dirname(__file__), 'assets')
    
    # 1. Contrastive Encoder
    src1 = os.path.join(assets, 'contrastive_encoder.keras')
    dst1 = os.path.join(assets, 'contrastive_encoder_fixed.keras')
    patch_keras_file(src1, dst1)
    
    # Also overwrite the clean one just in case
    dst1_clean = os.path.join(assets, 'contrastive_encoder_clean.keras')
    patch_keras_file(src1, dst1_clean)

    # 2. DriftNet Final
    src2 = os.path.join(assets, 'best_driftnet_final.keras')
    dst2 = os.path.join(assets, 'best_driftnet_final_fixed.keras')
    patch_keras_file(src2, dst2)

if __name__ == "__main__":
    main()
