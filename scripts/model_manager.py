import os
import sys
import subprocess
import requests
import json

def get_free_vram_mb():
    """Queries nvidia-smi to find the free GPU VRAM in MB.
    Returns None if query fails (e.g. command not found, no NVIDIA GPU)."""
    try:
        # Run nvidia-smi to get free memory
        cmd = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"]
        # In Windows shell can be necessary or subprocess.PIPE
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if lines:
            # Take the first GPU's free VRAM
            vram = int(lines[0].strip())
            return vram
    except Exception as e:
        # Log the error quietly but return None to indicate failure to monitor
        # In non-Nvidia environment or headless/non-supported OS, this falls back gracefully
        pass
    return None

def select_model(settings=None):
    """
    Dynamically selects the local model based on available free VRAM.
    Threshold is 10 GB (10240 MB).
    Primary: ministral-3-14b:latest
    Fallback: gemma4-e4b:latest
    """
    if settings is None:
        # Avoid circular import if needed, but generally safe to import here or pass
        settings = {}
        
    # Define default thresholds and models
    threshold_mb = settings.get("vram_threshold_mb", 10240) # 10 GB
    primary_model = settings.get("localModel") or "ministral-3-14b:latest"
    fallback_model = settings.get("localFallbackModel") or "gemma4-e4b:latest"
    
    free_vram = get_free_vram_mb()
    
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "model_manager.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if free_vram is None:
        # Could not read VRAM, default to primary
        selected = primary_model
        reason = "Could not query GPU (nvidia-smi not available or failed). Defaulting to primary."
    else:
        if free_vram >= threshold_mb:
            selected = primary_model
            reason = f"Free VRAM: {free_vram} MB is above threshold {threshold_mb} MB. Selected primary."
        else:
            selected = fallback_model
            reason = f"Free VRAM: {free_vram} MB is BELOW threshold {threshold_mb} MB. Selected fallback."
            
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {reason} -> MODEL: {selected}\n")
        
    print(f"    [Model Manager] {reason} Using: {selected}", file=sys.stderr)
    return selected

def unload_all_models(base_url="http://localhost:11434"):
    """
    Instructs Ollama to unload ALL active models by querying tags or using known models,
    releasing all VRAM.
    """
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "model_manager.log")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    endpoint = base_url.rstrip('/') + '/api/chat'
    tags_endpoint = base_url.rstrip('/') + '/api/tags'
    
    loaded_models = set()
    
    # Try to query all installed models to purge them
    try:
        r = requests.get(tags_endpoint, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("models", []):
                name = m.get("name")
                if name:
                    loaded_models.add(name)
    except Exception:
        pass
        
    # Fallback to hardcoded expected models if query fails
    if not loaded_models:
        loaded_models = {"ministral-3-14b:latest", "gemma4-e4b:latest", "llama3"}
        
    print(f"\n[Model Manager] Dispatching unload signal to reclaim VRAM from: {', '.join(loaded_models)}...", file=sys.stderr)
    
    unloaded = []
    for model in loaded_models:
        try:
            # keep_alive: 0 purges the model
            res = requests.post(endpoint, json={"model": model, "keep_alive": 0}, timeout=5)
            if res.status_code == 200:
                unloaded.append(model)
        except Exception:
            pass
            
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] Unloaded models: {', '.join(unloaded)}\n")
        
    print(f"[Model Manager] VRAM reclamation completed for: {', '.join(unloaded)}\n", file=sys.stderr)
    return unloaded

if __name__ == "__main__":
    print(f"Free VRAM: {get_free_vram_mb()} MB")
    print(f"Selected Model: {select_model()}")
