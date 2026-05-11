# FEAT-012: Hybrid Local-Cloud Intelligence & Failover

## 1. Overview
Empower the platform to utilize locally-hosted LLMs (via Ollama) for high-throughput operations while dynamically pivoting to cloud models for high-fidelity creative generation. Includes automated resource recovery hooks to maintain desktop health.

## 2. Impacted requirements
- `FR-065`: Intra-Local Model Failover
- `FR-066`: Automatic VRAM Reclamation (Eco-Hook)
- `FR-067`: Hybrid Intelligence Switching

## 3. Design description
The core LLM Router (`utils.py`) manages traffic shaping between local resources and external APIs.

### 3.1 Component Architecture
1.  **Router Override:** `call_llm()` modified to accept `provider_override` param. This gates high-risk calls (Drafting, Verification) explicitly to cloud tier.
2.  **Cascading Local Failover:** `_call_local()` encapsulates try-catch logic looping through `primary` -> `fallback` model definitions loaded from internal state.
3.  **Eco-Hook Handlers:** Native teardown routines triggered via Python `atexit` and standard `finally` blocks push `keep_alive: 0` payload to Ollama API to reclaim system memory instantly.

## 4. User interactions
- Zero user interactions required for normal switching; routing decisions reside inside the automation engine algorithms.
- Users notice dramatically reduced system VRAM usage between pipeline runs.
- Drafting engines maintain 100% hallucination-free fidelity even if local is set as primary global model.

## 5. Verification Plan
- **Automation:** Validated via `smoke_test_gemma.py` and standard unbuffered shell logging.
- **Manual:** Watch system memory task manager upon script completion to confirm immediate unloading.
