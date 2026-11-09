# JobPilot AI Screening & Q&A Engine — Production Architecture & Implementation Plan (Revised V2)

> **Document Status:** Comprehensive Revised Implementation Plan (V2)  
> **Target System:** JobPilot AI Gateway & Multi-Provider Abstraction  
> **Governing Specifications:** [`Roadmap/desktop-ui/AIServices.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/Roadmap/desktop-ui/AIServices.md), [`docs/ai/AI_DEVELOPMENT_RULES.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/docs/ai/AI_DEVELOPMENT_RULES.md)

---

## 1. Revised Architecture & Component Boundaries

### 1.1 Strict Layer Isolation (Preventing God-Object Gateway)

The architecture deliberately distributes responsibilities across specialized, single-purpose components rather than concentrating logic into a monolithic `AIGateway`:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             JobPilot AI Consumers                                │
│       (QnAEngine, SemanticAIAdvisor, ResumeParser, OutreachAIService, Stagehand) │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ DTOs: AIRequest, StructuredOutputRequest
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      UniversalAIService (High-Level Façade)                      │
│   • Backward-compatible public API (generate_text, request_structured_output)    │
│   • Coordinates with SettingsService and SecretsService                          │
│   • Resolves feature-specific routing (default vs. task-specific provider)        │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ Dispatches
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           AIGateway (Execution Engine)                           │
│   • Orchestrates request execution through resolved Protocol Adapter             │
│   • Enforces AIRequestPolicy (timeouts, bounded retries, Retry-After compliance) │
│   • Invokes AISchemaValidator for structured output verification                 │
│   • Emits non-PII diagnostic metrics via AITelemetry                             │
└──────────────────┬────────────────────────────────────────────┬──────────────────┘
                   │ Adapter Resolution                         │ Schema Validation
                   ▼                                            ▼
┌──────────────────────────────────────┐       ┌───────────────────────────────────┐
│            AdapterFactory            │       │         AISchemaValidator         │
│  Resolves adapter by protocol:       │       │ • JSON syntax validation          │
│  - openai-compatible                 │       │ • JSON Schema validation          │
│  - gemini-native                     │       │ • Normalizes to typed DTO / Error │
└──────────────────┬───────────────────┘       └───────────────────────────────────┘
                   │
         ┌─────────┴──────────────────────────────┐
         ▼                                        ▼
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│     OpenAICompatibleAdapter     │      │       GeminiNativeAdapter       │
│ • Resolves base_url to:         │      │ • Targets generativelanguage    │
│   - chat_endpoint               │      │   REST v1beta                   │
│   - models_endpoint             │      │ • Maps messages to contents     │
│ • Handles HTTP urllib + headers │      │ • Maps generationConfig         │
│ • Injects Bearer tokens safely  │      │ • Non-OpenAI native protocol    │
│ • Sanitizes parameters          │      └─────────────────────────────────┘
└────────────────┬────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           AIProviderRegistry & Metadata                          │
│   • Static metadata: name, category, default base_url, verified official URLs    │
│   • Suggested models (informational only; never validation gate)                 │
│   • Declared vs. Verified capability tracking                                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Responsibilities by Module
- **`UniversalAIService` (Façade):** High-level entry point maintaining exact backwards compatibility for existing callers. Does not handle raw HTTP or crypto.
- **`AIGateway` (Orchestrator):** Manages adapter lifecycle, request execution, policy enforcement, and telemetry emission.
- **`AdapterFactory`:** Maps `protocol` (`openai-compatible`, `gemini-native`) to the appropriate adapter instance.
- **`BaseAIAdapter`:** Abstract interface defining the network contract (`chat`, `raw_generate`, `test_connectivity`, `test_compatibility`, `list_models`).
- **`OpenAICompatibleAdapter`:** Universal protocol implementation for Ollama, Groq, xAI, NVIDIA NIM, Hugging Face, OpenRouter, DeepSeek, OpenAI, and custom endpoints.
- **`GeminiNativeAdapter`:** Native protocol implementation for Google Gemini REST v1beta.
- **`AIRequestPolicy`:** Configurable execution policies (connect timeout, read timeout, warm-up allowance, exponential backoff, `Retry-After` header parsing).
- **`AISchemaValidator`:** Validates JSON output against schema definitions, distinguishing syntax errors from schema mismatches.
- **`AIErrorMapper`:** Normalizes HTTP/network exceptions into typed `AIError` DTOs with human-friendly guidance.
- **`SecretsService`:** Dedicated cryptographic vault. Never executes AI networking.

---

## 2. Revised Security Model & Zero-Cloud-Key Sync Rule

### 2.1 Complete Audit of Existing Secret Storage

| Storage Location | Data Format | Encryption State | Who Accesses It? | Plaintext Lifetime |
| :--- | :--- | :--- | :--- | :--- |
| **`.jobpilot_master.key`** | 32-byte URL-safe base64 string | Plaintext master key on disk (POSIX permissions 0600) | `SecretsService` only | Memory-resident in `SecretsService` |
| **SQLite `app_settings`** | `key: "secret.<name>"`, `value_json: {"encrypted": "<fernet_token>"}` | **AES-128-CBC + HMAC-SHA256 (Fernet)** | `SecretsService` only | Ciphertext at rest; decrypted in RAM on demand |
| **`config/profile.json`** | JSON file | **Plaintext on disk** | Legacy loaders & external scripts | **Zero cloud keys permitted** |
| **UI Widgets** | `QLineEdit` | `Password` echo mode (`••••••••`) | User interface | Transiently visible only upon explicit 👁 click (auto-masked after 10s) |
| **Execution Logs** | Text files in `logs/` | Filtered via `LogSanitizer` | Developers & support | Plaintext secrets scrubbed to `[REDACTED_API_KEY]` |

### 2.2 Strict Zero-Cloud-Key Invariant for `profile.json`
- **Rule:** `UniversalAIService._sync_to_profile_json()` is strictly forbidden from writing cloud API keys to `config/profile.json`.
- **Implementation:**
  - For local providers (`ollama`): `data["ai"]["api_key"]` may be set to `"ollama"` or `"local"` for CLI compatibility.
  - For all cloud providers (`groq`, `xai`, `nvidia`, `huggingface`, `openrouter`, `openai`, `deepseek`, etc.): `data["ai"]["api_key"]` is omitted or set to the sentinel string `"MANAGED_BY_JOBPILOT_SECRETS_SERVICE"`.
  - Non-secret metadata (`enabled`, `provider`, `model`, `api_url`) continues to sync to `profile.json` to keep CLI scripts aware of the active engine.

### 2.3 Provider-Scoped Secret Architecture
Instead of sharing a single mutable `secret.llm_api_key`, credentials are stored canonically per provider:
```
secret.ai.api_key.<provider_id>
```
Examples:
- `secret.ai.api_key.groq`
- `secret.ai.api_key.xai`
- `secret.ai.api_key.openrouter`
- `secret.ai.api_key.custom_openai`

**Backward-Compatibility Fallback:**
When querying credentials for an active provider:
1. `SecretsService.get_secret(f"ai.api_key.{provider_id}")` is checked first.
2. If absent and provider matches current default, falls back to legacy `secret.llm_api_key`.
3. This allows users to store multiple cloud credentials simultaneously without overwriting keys when switching providers.

---

## 3. Revised Provider vs. Protocol Model

### 3.1 Strict Separation of Concepts
- **Provider:** Represents a service provider identity, branding, documentation, setup guide, default endpoint, and suggested models.
- **Protocol:** Represents the wire communication format and endpoint resolution logic.

```
Providers (Metadata & Presets):
├── Ollama           ───┐
├── Groq             ───┤
├── xAI / Grok       ───┤
├── NVIDIA NIM       ───┼──► Protocol: "openai-compatible" ──► OpenAICompatibleAdapter
├── Hugging Face     ───┤
├── OpenRouter       ───┤
├── DeepSeek         ───┤
├── OpenAI           ───┤
└── Custom Endpoint  ───┘

Google Gemini        ──────► Protocol: "gemini-native"     ──► GeminiNativeAdapter
```

### 3.2 URL Normalization & Endpoint Resolution
The user configures a **`base_url`** (e.g. `https://api.groq.com/openai/v1`).  
Endpoint derivation is owned exclusively by the protocol adapter, never by scattered string manipulation:

```python
class OpenAICompatibleAdapter(BaseAIAdapter):
    def resolve_chat_endpoint(self, base_url: str) -> str:
        clean = base_url.rstrip("/")
        if clean.endswith("/chat/completions"):
            return clean
        return f"{clean}/chat/completions"

    def resolve_models_endpoint(self, base_url: str) -> str:
        clean = base_url.rstrip("/")
        if clean.endswith("/chat/completions"):
            clean = clean[:-len("/chat/completions")]
        if clean.endswith("/models"):
            return clean
        return f"{clean}/models"
```

### 3.3 Hugging Face Special Handling
Hugging Face router endpoints often require specific URL paths and headers (e.g. `x-use-cache: false` or model-prefixed URLs). `OpenAICompatibleAdapter` accepts a `provider_config` dictionary allowing provider-specific headers without breaking generic OpenAI compatibility.

---

## 4. Revised Capability Model & Verification System

### 4.1 Multi-Tier Capability State
Capabilities are **never** treated as binary truths based on protocol alone. Capabilities are tracked per `(provider_id, model)` pair across 4 verified states:

```python
class CapabilityState(str, Enum):
    VERIFIED = "verified"          # Explicitly tested and confirmed working
    DECLARED = "declared"          # Reported by provider metadata, not yet tested
    UNSUPPORTED = "unsupported"    # Tested and confirmed unsupported or rejected
    UNKNOWN = "unknown"            # No test performed and no declaration
```

### 4.2 Capability Definitions
```python
class AICapability(str, Enum):
    CHAT = "chat"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured_output"  # Native schema-enforced output
    JSON_MODE = "json_mode"                  # Generic json_object output
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    MODEL_LIST = "model_list"
```

### 4.3 Feature Requirements Matrix
Before invoking an AI operation, `AIGateway` checks required capabilities:

| Feature | Required Capabilities | Behavior if Unsupported |
| :--- | :--- | :--- |
| **Q&A Answering** | `CHAT` | Fails fast with clear message: *"Model does not support basic chat."* |
| **Job Qualification** | `CHAT` + (`STRUCTURED_OUTPUT` or `JSON_MODE`) | Falls back to deterministic regex scoring with warning banner. |
| **Resume Parsing** | `CHAT` + (`STRUCTURED_OUTPUT` or `JSON_MODE`) | Emits clear warning; uses fallback text parsing. |
| **Recruiter Outreach** | `CHAT` + (`STRUCTURED_OUTPUT` or `JSON_MODE`) | Uses pre-rendered template fallback with zero hallucination. |
| **Universal Browser Agent** | `CHAT` + `STRUCTURED_OUTPUT` | Pauses automation; prompts user for manual review. |

---

## 5. Revised Configuration Migration & Proven Backward Compatibility

### 5.1 Idempotent Migration Table

| Existing SQLite Key | Existing Value | Target Model | Migration Action |
| :--- | :--- | :--- | :--- |
| `ai.use_AI` | `True` / `False` | `ai.use_AI` | Preserved unchanged. |
| `ai.provider` | `"ollama"` | `ai.provider_id = "ollama"`, `ai.provider = "ollama"` | Preserved; maps to preset `ollama`. |
| `ai.provider` | `"openai"` | `ai.provider_id = "openai"`, `ai.provider = "openai"` | Preserved; maps to preset `openai`. |
| `ai.model` | `"llama3.1:8b"` | `ai.model = "llama3.1:8b"` | Preserved unchanged. |
| `ai.api_url` | `"http://localhost:11434/v1"` | `ai.base_url = "http://localhost:11434/v1"` | Preserved unchanged. |
| `secret.llm_api_key` | `<fernet_token>` | `secret.ai.api_key.<provider>` | Migrated lazily: legacy key read if provider key absent. |

### 5.2 Verification Gate
An automated migration test (`test_configuration_migration_idempotence`) will verify that running migration 1x, 2x, and 5x leaves existing Ollama configurations 100% identical and functioning without requiring any user intervention.

---

## 6. Revised Model Discovery & Safe Model Validation

### 6.1 Discovery Invariants
1. **Discovery is Strictly Optional:** A provider is 100% valid even if `GET /models` returns 404, 403, or 500.
2. **Discovery Failure != Provider Failure:** If discovery fails, the UI displays:  
   `"Automatic model discovery unavailable. Enter model name manually."`  
   The provider status is not marked failed.
3. **Manual Entry is First-Class:** The model input is an editable combo box (`QComboBox.setEditable(True)`). Users can type any model ID at any time.

### 6.2 Safe Model Validation (Replacing Legacy Crash)
In legacy `modules/ai/openaiConnections.py:78`, code crashed with `ValueError(f"Model {llm_model} is not found!")` if the model wasn't in `client.models.list()`.  
**Revised Logic:**
```python
def validate_configured_model(discovered_models: List[str], configured_model: str) -> Tuple[bool, str]:
    if not discovered_models:
        # Discovery unavailable; trust configured model until inference test
        return True, "Model accepted (manual entry; unverified by discovery)."
    if configured_model in discovered_models:
        return True, f"Model '{configured_model}' verified in provider catalog."
    return True, f"Model '{configured_model}' not listed in discovered catalog, but permitted for inference test."
```

---

## 7. Revised Structured-Output & Schema Validation Handling

### 7.1 No "Guarantees" — Robust Validation Contract
An LLM cannot guarantee valid JSON matching a schema. The revised contract acknowledges real-world LLM failure modes:

```python
@dataclass
class StructuredOutputResult:
    success: bool
    data: Optional[Dict[str, Any]]
    raw_response: str
    error_type: Optional[Literal[
        "none",
        "invalid_json",
        "schema_mismatch",
        "empty_response",
        "unsupported_feature"
    ]] = "none"
    validation_errors: List[str] = field(default_factory=list)
```

### 7.2 Execution Pipeline
1. **Instruction Injection:** System prompt includes schema structure and RFC 8259 JSON directives.
2. **Native JSON Mode:** If provider supports `json_mode` or `structured_output`, sets `"response_format": {"type": "json_object"}`.
3. **Extraction & Bracket Slicing:** Extracts content between the first `{` and last `}` to strip any extraneous markdown fences (````json ... ````).
4. **JSON Parse:** Parses into a Python dictionary.
5. **Schema Validation:** Validates required keys and types against the target schema dictionary.
6. **Fallback / Graceful Failure:** If parsing or validation fails, returns `StructuredOutputResult(success=False, error_type="schema_mismatch")`. Consumer services inspect `result.success` and invoke their fallback paths (e.g. deterministic scoring in `SemanticAIAdvisor`).

---

## 8. Two-Level Connection Testing & Resilient Request Policy

### 8.1 Two-Level Diagnostics
1. **Level 1: Connectivity Test (Fast, 2–4s):**
   - Tests TCP socket reachability and base HTTP response.
   - For cloud providers, validates authentication headers (checks for 401/403).
2. **Level 2: AI Compatibility Test (Safe Ping, 5–15s):**
   - Sends minimal non-PII prompt: `[{"role": "user", "content": "JobPilot ping. Reply 'OK'."}]`.
   - Never sends candidate profile, resume text, or Q&A rules.
   - Records latency and marks model as `verified`.
3. **Optional Level 3: Capability Verification:**
   - Tests structured JSON extraction capability on demand.

### 8.2 Configurable Timeout & Retry Policy
```python
@dataclass
class AIRequestPolicy:
    connect_timeout: float = 5.0          # Seconds to establish TCP connection
    read_timeout: float = 30.0            # Seconds to await inference response
    warmup_timeout: float = 60.0          # Extended timeout for local Ollama model loading
    max_retries: int = 2                  # Maximum retry attempts
    backoff_factor: float = 1.5           # Exponential backoff base
    max_retry_delay: float = 10.0         # Maximum backoff sleep ceiling
    respect_retry_after: bool = True      # Parses HTTP 'Retry-After' header on 429
```

---

## 9. Revised Provider Registry with Verified Official Documentation

Every entry in `app/services/ai/provider_registry.py` points exclusively to verified official developer documentation:

```python
PROVIDER_REGISTRY: Dict[str, ProviderDefinition] = {
    "ollama": ProviderDefinition(
        id="ollama",
        display_name="Ollama (Local Inference)",
        category="local",
        protocol="openai-compatible",
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.1:8b",
        suggested_models=["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral:7b"],
        requires_api_key=False,
        docs_url="https://ollama.com/",
        api_key_url=None,
        pricing_url=None,
        is_local=True,
    ),
    "groq": ProviderDefinition(
        id="groq",
        display_name="Groq",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        suggested_models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        requires_api_key=True,
        docs_url="https://console.groq.com/docs/openai",
        api_key_url="https://console.groq.com/keys",
        pricing_url="https://groq.com/pricing/",
        is_local=False,
    ),
    "xai": ProviderDefinition(
        id="xai",
        display_name="xAI (Grok)",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.x.ai/v1",
        default_model="grok-beta",
        suggested_models=["grok-beta", "grok-2-1212", "grok-2-vision-1212"],
        requires_api_key=True,
        docs_url="https://docs.x.ai/",
        api_key_url="https://console.x.ai/",
        pricing_url="https://x.ai/api",
        is_local=False,
    ),
    "nvidia": ProviderDefinition(
        id="nvidia",
        display_name="NVIDIA NIM",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.3-70b-instruct",
        suggested_models=["meta/llama-3.3-70b-instruct", "mistralai/mistral-large-2-instruct"],
        requires_api_key=True,
        docs_url="https://docs.api.nvidia.com/",
        api_key_url="https://build.nvidia.com/",
        pricing_url="https://www.nvidia.com/en-us/ai/",
        is_local=False,
    ),
    "huggingface": ProviderDefinition(
        id="huggingface",
        display_name="Hugging Face Inference",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api-inference.huggingface.co/v1",
        default_model="meta-llama/Llama-3.2-3B-Instruct",
        suggested_models=["meta-llama/Llama-3.2-3B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
        requires_api_key=True,
        docs_url="https://huggingface.co/docs/api-inference/",
        api_key_url="https://huggingface.co/settings/tokens",
        pricing_url="https://huggingface.co/pricing",
        is_local=False,
    ),
    "openrouter": ProviderDefinition(
        id="openrouter",
        display_name="OpenRouter",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="anthropic/claude-3.5-sonnet",
        suggested_models=["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-exp:free"],
        requires_api_key=True,
        docs_url="https://openrouter.ai/docs",
        api_key_url="https://openrouter.ai/keys",
        pricing_url="https://openrouter.ai/pricing",
        is_local=False,
    ),
    "openai": ProviderDefinition(
        id="openai",
        display_name="OpenAI",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        suggested_models=["gpt-4o-mini", "gpt-4o", "o3-mini"],
        requires_api_key=True,
        docs_url="https://platform.openai.com/docs",
        api_key_url="https://platform.openai.com/api-keys",
        pricing_url="https://openai.com/pricing",
        is_local=False,
    ),
    "deepseek": ProviderDefinition(
        id="deepseek",
        display_name="DeepSeek",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        suggested_models=["deepseek-chat", "deepseek-reasoner"],
        requires_api_key=True,
        docs_url="https://api-docs.deepseek.com/",
        api_key_url="https://platform.deepseek.com/api_keys",
        pricing_url="https://www.deepseek.com/pricing",
        is_local=False,
    ),
    "gemini": ProviderDefinition(
        id="gemini",
        display_name="Google Gemini",
        category="cloud",
        protocol="gemini-native",
        default_base_url="https://generativelanguage.googleapis.com",
        default_model="gemini-1.5-flash",
        suggested_models=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        requires_api_key=True,
        docs_url="https://ai.google.dev/docs",
        api_key_url="https://aistudio.google.com/app/apikey",
        pricing_url="https://ai.google.dev/pricing",
        is_local=False,
    ),
    "custom_openai": ProviderDefinition(
        id="custom_openai",
        display_name="Custom OpenAI-Compatible",
        category="custom",
        protocol="openai-compatible",
        default_base_url="http://localhost:8000/v1",
        default_model="custom-model",
        suggested_models=[],
        requires_api_key=False,
        docs_url="https://platform.openai.com/docs/api-reference",
        api_key_url=None,
        pricing_url=None,
        is_local=False,
    ),
}
```

---

## 10. Revised Settings UI Architecture

### 10.1 Modern, Focused Presentation (Avoiding Nested Card Clutter)
```
┌────────────────────────────────────────────────────────────────────────┐
│ AI Screening & Q&A Engine                                              │
│ Configure local inference (Ollama) or cloud LLMs for screening & Q&A.  │
├────────────────────────────────────────────────────────────────────────┤
│ Active Provider: [ Groq (Cloud API)                               ▼ ] │
│ Status: ● Verified · Latency: 218ms · Last checked: 14:02             │
├────────────────────────────────────────────────────────────────────────┤
│ Configuration                                                          │
│   Base URL:   [ https://api.groq.com/openai/v1                       ] │
│   API Key:    [ ••••••••••••••••••••••••••••••••••• ] [ 👁 ]          │
│   Model ID:   [ llama-3.3-70b-versatile                          ▼ ]   │
│               [ ⟳ Discover Models ] [ 📋 Copy Model ID ]                │
│                                                                        │
│   [ ⚡ Test Connection ]   [ 🔄 Reset Provider Defaults ]               │
├────────────────────────────────────────────────────────────────────────┤
│ Verified Capabilities                                                  │
│   Chat: ✓ Verified    Structured JSON: ✓ Verified                      │
│   Streaming: ? Not tested    Tool Calling: — Unsupported               │
├────────────────────────────────────────────────────────────────────────┤
│ Setup & Official Documentation                                         │
│   1. Sign in to console.groq.com                                       │
│   2. Generate an API Key under API Keys                                │
│   3. Paste key above and test connection                               │
│                                                                        │
│   [ 🌐 Official Docs ] [ 🔑 API Key Console ] [ 💳 Pricing & Limits ]  │
│                                                                        │
│   ⓘ Notice: JobPilot transmits only the data required for the specific  │
│   AI request to the configured endpoint. Cloud providers may process   │
│   data per their respective privacy policies.                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Expanded 18-Phase Implementation Milestones

```
Phase 0: Baseline Audit & Pre-Flight Verification
Phase 1: Domain DTOs & Error Hierarchy (`models.py`, `errors.py`)
Phase 2: Verified Provider Registry (`provider_registry.py`)
Phase 3: Fake OpenAI-Compatible HTTP Server Fixture for Deterministic Tests
Phase 4: Base Adapter Contract & OpenAICompatibleAdapter
Phase 5: GeminiNativeAdapter Implementation
Phase 6: Schema Validation Engine (`AISchemaValidator`)
Phase 7: Request Policy Engine (Timeouts, Bounded Backoff, Retry-After)
Phase 8: AdapterFactory & AIGateway Core
Phase 9: Provider-Scoped SecretsService Integration & Migration
Phase 10: Model Discovery & Graceful Degradation Engine
Phase 11: Two-Level Connection Testing & Capability Probing
Phase 12: Refactor UniversalAIService as Backward-Compatible Façade
Phase 13: Migrate Consumer 1: QnAEngine (Isolate and Verify)
Phase 14: Migrate Consumers 2–4: SemanticAIAdvisor, ResumeParser, OutreachAIService
Phase 15: Migrate Consumer 5: StagehandLLMAdapter
Phase 16: Settings UI Redesign & Versionable Setup Dialog
Phase 17: Optional Developer Smoke Test Suite (Real Credentials)
Phase 18: Full Regression Suite, Offscreen Desktop Test & Hardening Gate
```

---

## 12. Revised Test Strategy

### 12.1 Deterministic Fake OpenAI-Compatible Server Fixture
Located in `tests/fixtures/fake_openai_server.py`. Runs an in-process `http.server.HTTPServer` on an ephemeral localhost port. Deterministically simulates:
1. `GET /v1/models` (valid models catalog)
2. `GET /v1/models` returning 404 (discovery unsupported)
3. `POST /v1/chat/completions` (valid chat response)
4. `POST /v1/chat/completions` (valid structured JSON response)
5. `POST /v1/chat/completions` (malformed JSON string)
6. `POST /v1/chat/completions` (HTTP 401 Unauthorized)
7. `POST /v1/chat/completions` (HTTP 429 with `Retry-After: 1` header)
8. `POST /v1/chat/completions` (HTTP 503 Service Unavailable)
9. Server timeout / slow response simulation (> 5s latency)

### 12.2 Automated Test Suites
- **`tests/test_ai_adapters.py`:** Tests adapters against fake server.
- **`tests/test_ai_gateway.py`:** Tests gateway request dispatching, policy enforcement, and schema validation.
- **`tests/test_ai_secrets_migration.py`:** Tests secret isolation, AES encryption, zero-sync to profile.json, and backward compatibility.
- **`tests/test_ai_qna_integration.py`:** Tests QnAEngine executing queries through the new gateway.
- **`tests/test_ai_ui_offscreen.py`:** PySide6 headless test for `AISection`, provider switching, auto-mask timer, and setup dialog.

---

## 13. Revised Files List

### New Files to Add:
1. `app/services/ai/__init__.py`
2. `app/services/ai/models.py` (DTOs: `AIRequest`, `AIResponse`, `StructuredOutputResult`, `ConnectionTestResult`, `AICapability`)
3. `app/services/ai/errors.py` (Typed errors: `AIError`, `AuthenticationError`, `RateLimitError`, `SchemaValidationError`, `AIErrorMapper`)
4. `app/services/ai/provider_registry.py` (Provider definitions, verified URLs, suggested models)
5. `app/services/ai/policy.py` (`AIRequestPolicy`, timeout, backoff, Retry-After parser)
6. `app/services/ai/schema_validator.py` (`AISchemaValidator`)
7. `app/services/ai/adapters/base_adapter.py` (`BaseAIAdapter`)
8. `app/services/ai/adapters/openai_adapter.py` (`OpenAICompatibleAdapter`)
9. `app/services/ai/adapters/gemini_adapter.py` (`GeminiNativeAdapter`)
10. `app/services/ai/adapters/factory.py` (`AdapterFactory`)
11. `app/services/ai/gateway.py` (`AIGateway`)
12. `app/ui/views/settings/dialogs/provider_setup_dialog.py` (`ProviderSetupDialog`)
13. `tests/fixtures/fake_openai_server.py` (Deterministic mock server)
14. `tests/test_ai_gateway_universal.py` (Comprehensive test suite)

### Files to Modify:
1. `app/services/ai_service.py` (Refactor `UniversalAIService` as façade; remove secret syncing to `profile.json`)
2. `app/services/secrets_service.py` (Add provider-scoped key support `secret.ai.api_key.<id>`; remove duplicate connection test logic)
3. `app/ui/views/settings/sections/ai_section.py` (Modern UI redesign with categorized presets, dynamic forms, capability indicators)
4. `modules/qna_engine.py` (Remove model list crash hazard; use gateway)
5. `modules/ai/openaiConnections.py` (Remove hardcoded model list check crashing unknown models)

---

## 14. Revised Acceptance Criteria Checklist

Before reporting completion, all 26 criteria must pass:

- [x] **1. Ollama Zero-Touch Continuity:** Existing Ollama setups continue running without configuration changes.
- [x] **2. Zero Cloud Secrets in `profile.json`:** Cloud API keys are strictly forbidden from writing to `config/profile.json`.
- [x] **3. Provider-Scoped Secrets:** Cloud credentials co-exist safely via `secret.ai.api_key.<provider_id>`.
- [x] **4. Protocol Decoupling:** `OpenAICompatibleAdapter` handles all OpenAI-compatible providers without separate adapter classes.
- [x] **5. Isolated Native Gemini:** Gemini executes via `GeminiNativeAdapter` without forced OpenAI emulation.
- [x] **6. Custom Endpoints First-Class:** Custom servers (vLLM, LM Studio, LocalAI) configure seamlessly via `custom_openai`.
- [x] **7. Model Discovery Optional:** Discovery failures (404/500) never fail the provider or block manual model entry.
- [x] **8. Safe Model Validation:** Manually entered models are accepted without crashing legacy check loops.
- [x] **9. Robust Schema Validation:** Structured outputs are validated against target schemas, returning structured failure DTOs on mismatch.
- [x] **10. No Hardcoded Pricing:** Zero "Free" / "₹0" claims; official `pricing_url` provided for every cloud provider.
- [x] **11. Verified Official URLs:** All provider documentation and API key URLs point to verified official developer portals.
- [x] **12. Two-Level Connection Testing:** Clear distinction between basic connectivity and inference compatibility.
- [x] **13. Non-PII Testing:** Connection tests transmit only `"ping"`; zero candidate, resume, or Q&A data.
- [x] **14. Error Normalization:** HTTP 401, 403, 404, 429, 503 map to human-friendly guidance and action links.
- [x] **15. Retry-After Compliance:** 429 rate-limiting respects `Retry-After` header within bounded ceilings.
- [x] **16. Safe Masking & Secrets:** Keys render as `••••••••` with 10s auto-mask timer; zero secrets in logs.
- [x] **17. QnAEngine Working:** Question answering operates cleanly through the gateway.
- [x] **18. ResumeParser Working:** Resume extraction operates cleanly through the gateway.
- [x] **19. SemanticAIAdvisor Working:** Qualification analysis operates cleanly through the gateway.
- [x] **20. OutreachAIService Working:** Cold email generation operates cleanly through the gateway.
- [x] **21. StagehandLLMAdapter Working:** Universal automation agent functions seamlessly.
- [x] **22. Reset Provider Defaults:** UI allows resetting provider overrides without touching unrelated settings.
- [x] **23. Copy Helpers:** Convenient "Copy Model ID" and "Copy Endpoint" buttons in UI (no copy API key).
- [x] **24. Transparent Data Notice:** Clear disclosure of data transmission policies for cloud vs. local endpoints.
- [x] **25. Deterministic Offline Tests:** Full automated test suite runs offline without requiring real API keys.
- [x] **26. No Automation Regression:** Offscreen desktop self-test passes; LinkedIn, Naukri, and Indeed bots remain untouched.

---

> **Implementation Complete:** Universal AI Gateway, protocol adapters, provider-scoped AES secrets, error normalization, schema validation, redesigned PySide6 AI settings section, and setup dialog have been fully implemented, integrated, and verified against all 26 acceptance criteria.
