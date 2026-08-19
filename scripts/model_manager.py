"""Ollama / local-model VRAM helpers.

OPT-IN FALLBACK (CR-070 / CR-017): kept intact per Jason's instruction not to
delete local-LLM call sites. Default generate-submission authoring does not
use this. Do not archive as dead code.
"""
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
    Threshold is 7.5 GB (7500 MB) — sized for llama3.1:8b-q5_K_M (~6GB) with headroom.
    Primary: llama3.1:8b-instruct-q5_K_M
    Fallback: same primary by default (phi produced unusable draft quality).
    """
    if settings is None:
        settings = {}

    # Define default thresholds and models
    threshold_mb = settings.get("vram_threshold_mb", 7500)  # 7.5 GB
    primary_model = settings.get("localModel") or "llama3.1:8b-instruct-q5_K_M"
    fallback_model = settings.get("localFallbackModel") or primary_model
    
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

def ensure_ollama_running(base_url="http://localhost:11434", timeout_sec=30):
    """Check whether the local Ollama server is reachable; if not, trigger
    the installed Ollama client to start it and wait for it to come up.

    Added 2026-08-18 -- this was supposed to land alongside the Stage 0
    "default to a local LLM call" change (2026-08-17, build_stage0_fit_gate.py)
    but was missed, so every local call silently fell back to the
    deterministic regex extractor on any machine where Ollama wasn't
    already running, with no attempt to start it first.

    Any `ollama` CLI subcommand auto-launches the installed background
    app/server if it isn't already running (confirmed on this machine:
    `ollama list` printed "starting Ollama" / "starting ollama server" to
    its own log and the API was reachable within ~3s). Shelling out to a
    lightweight subcommand and then polling the API is what "standing it
    up" means here -- there is no separate service to install or manage.

    Returns True once the API responds, False if it never comes up within
    *timeout_sec*. Callers must treat False exactly like any other local-call
    failure (fall back to the deterministic/non-local path) -- this never
    changes the existing safety contract, it only makes the LLM path
    succeed more often when Ollama is installed but not yet started.
    """
    import time

    tags_url = base_url.rstrip("/") + "/api/tags"

    def _reachable():
        try:
            return requests.get(tags_url, timeout=2).status_code == 200
        except Exception:
            return False

    if _reachable():
        return True

    print("    [Ollama] Server not reachable -- attempting to start it...", file=sys.stderr)
    try:
        # Fire-and-forget: do NOT use capture_output/PIPE + wait() here. The
        # `ollama list` subcommand triggers the installed client to launch its
        # own background app process, which inherits stdout/stderr handles
        # from this call -- if we pipe and wait, Python's cleanup blocks
        # forever after a timeout because that inherited pipe never closes,
        # even though the server itself is already reachable within a few
        # seconds (confirmed 2026-08-18: curl succeeded while the launcher
        # subprocess was still hung waiting on its own pipe). Redirect to
        # DEVNULL (real file handles, not pipes) and never wait on it --
        # readiness is decided by polling the API below, not by this
        # process's exit.
        subprocess.Popen(
            ["ollama", "list"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("    [Ollama] 'ollama' CLI not found on PATH -- cannot auto-start.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"    [Ollama] Auto-start attempt failed: {e}", file=sys.stderr)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _reachable():
            print("    [Ollama] Server is up.", file=sys.stderr)
            return True
        time.sleep(1)

    print(f"    [Ollama] Server still unreachable after {timeout_sec}s -- falling back.", file=sys.stderr)
    return False


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
        loaded_models = {"llama3.1:8b-instruct-q5_K_M", "phi3.5:3.8b-mini-instruct-q8_0", "llama3"}
        
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
