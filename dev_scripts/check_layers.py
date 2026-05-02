import zipfile, json
with zipfile.ZipFile('assets/best_driftnet_final.keras', 'r') as zf:
    cfg = json.loads(zf.read('config.json'))
    for layer in cfg['config']['layers']:
        print(f"{layer.get('class_name')}: {layer.get('name')}")
