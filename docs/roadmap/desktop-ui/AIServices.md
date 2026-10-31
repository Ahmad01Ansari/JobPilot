You are working on JobPilot, a PySide6 desktop application for job-search,
recruitment workflow, resume management, Q&A, screening, automation and
AI-assisted job applications.

I want to redesign and productionize the existing AI Screening & Q&A Engine.

IMPORTANT:

Do NOT assume users have OpenAI.

Many users will use:

- Ollama/local models
- Groq
- xAI / Grok
- NVIDIA NIM / NVIDIA API
- Hugging Face
- OpenRouter
- Together
- Fireworks
- DeepInfra
- other OpenAI-compatible providers
- custom/self-hosted OpenAI-compatible endpoints
- eventually native provider APIs

The goal is:

    ONE JOBPILOT AI INTERFACE
             ↓
    ANY SUPPORTED AI PROVIDER
             ↓
    ANY COMPATIBLE MODEL

The user should be able to enter:

    Provider
    Endpoint URL
    API Key
    Model

and JobPilot should determine whether the configuration works.

The system must also guide users on:

    Where do I get the API key?
    What endpoint should I use?
    What model should I select?
    Is this provider free / paid / limited?
    Does this provider support the feature I am trying to use?
    Where is the official documentation?
    How do I create the key?

Do NOT hardcode temporary pricing/free-tier claims.
Provider pricing and free limits change frequently.

Official provider documentation should be treated as the source of truth.

============================================================
PHASE 0 — AUDIT THE EXISTING AI ARCHITECTURE FIRST
============================================================

Before writing code, inspect the entire existing AI stack.

Find and document:

- UniversalAIService
- existing AI service classes
- QnAService
- SecretsService
- SettingsService
- profile/config handling
- AI configuration keys
- Ollama integration
- OpenAI integration
- model discovery
- Q&A engine
- screening engine
- resume/job matching AI
- any LangChain/LangGraph usage
- any direct HTTP calls
- any direct OpenAI SDK calls
- any direct Ollama calls
- tests
- current Settings UI

Also inspect:

    app/services/
    app/ui/views/settings/
    config/
    tests/

Do not assume the architecture from documentation.

Create a current-state map:

    UI
      ↓
    current AI configuration
      ↓
    AI service
      ↓
    provider
      ↓
    model

Identify every place that currently assumes:

    OpenAI
    Ollama
    a fixed endpoint
    a fixed API format
    a fixed model name

Do not implement until this audit is complete.

============================================================
PHASE 1 — DEFINE THE AI PROVIDER ABSTRACTION
============================================================

Introduce a provider-agnostic architecture.

Recommended:

    AI Gateway
        ↓
    AI Provider Adapter
        ↓
    Model

Conceptually:

    AIService
        |
        +── OllamaAdapter
        +── OpenAICompatibleAdapter
        +── NativeProviderAdapter(s)
        +── Future adapters

The application must NOT contain provider-specific logic throughout
QnAService, ScreeningService, ResumeService, etc.

Those services should depend on a common AI interface.

For example:

    AIClient
        chat(...)
        stream(...)
        test_connection(...)
        list_models(...)
        capabilities()

Do not blindly copy this API.
Adapt it to the existing JobPilot architecture after inspecting the code.

============================================================
PHASE 2 — SUPPORT OPENAI-COMPATIBLE ENDPOINTS AS THE PRIMARY UNIVERSAL
INTERFACE
============================================================

This is the most important architectural decision.

A large number of providers expose OpenAI-compatible interfaces.

Examples currently include:

    Groq
    xAI
    NVIDIA NIM
    OpenRouter
    Hugging Face chat inference
    Ollama
    many self-hosted servers

Groq documents an OpenAI-compatible base URL.
xAI documents OpenAI REST compatibility.
NVIDIA NIM exposes OpenAI-compatible inference endpoints.
Hugging Face provides an OpenAI-compatible chat endpoint as well as its
native InferenceClient.

Therefore JobPilot should support a generic:

    OpenAICompatibleProvider

with:

    base_url
    api_key
    model
    timeout
    organization/project if applicable
    extra headers if required
    provider metadata

Example conceptual configuration:

    Provider Type:
        OpenAI Compatible

    Display Name:
        Groq

    Base URL:
        https://api.groq.com/openai/v1

    API Key:
        ********

    Model:
        <provider model>

The exact URLs/models must come from provider configuration or official
documentation, not assumptions.

============================================================
PHASE 3 — DO NOT CONFUSE PROVIDER WITH ENDPOINT
============================================================

Separate these concepts.

Provider:

    Groq

Endpoint:

    https://api.groq.com/openai/v1

Model:

    provider-specific model ID

Protocol:

    OpenAI-compatible

Authentication:

    API key

Capabilities:

    chat
    streaming
    structured output
    tool calling
    vision
    embeddings
    etc.

A user should be able to create:

    Custom OpenAI-Compatible Provider

without JobPilot knowing the provider name.

Example:

    Provider Name:
        My Local Server

    Protocol:
        OpenAI Compatible

    Endpoint:
        http://localhost:8000/v1

    API Key:
        optional

    Model:
        my-model

This is essential for future-proofing.

============================================================
PHASE 4 — PROVIDER REGISTRY
============================================================

Create a provider registry.

Conceptually:

    AIProviderRegistry

It should contain metadata such as:

    provider_id
    display_name
    protocol
    default_endpoint
    documentation_url
    api_key_url
    setup_guide_url
    model_catalog_url
    capabilities
    requires_api_key
    supports_local
    supports_model_discovery

Example provider definitions:

    ollama
    openai
    groq
    xai
    nvidia
    huggingface
    openrouter
    custom_openai_compatible

Do NOT hardcode provider behavior into the UI.

The UI should read provider metadata from the registry.

============================================================
PHASE 5 — PROVIDER CAPABILITY MODEL
============================================================

Do not assume every model/provider supports every AI feature.

Define capabilities.

For example:

    CHAT
    STREAMING
    STRUCTURED_OUTPUT
    JSON_MODE
    TOOL_CALLING
    VISION
    EMBEDDINGS
    MODEL_LIST
    REASONING

Potentially:

    RAG
    CLASSIFICATION
    FUNCTION_CALLING

But only expose capabilities that the provider/model actually supports.

The UI should communicate:

    ✓ Supported
    ⚠ Limited
    — Not available
    ? Unknown

Do NOT treat "OpenAI compatible" as meaning "100% OpenAI feature compatible."

Compatibility can be partial.

============================================================
PHASE 6 — MODEL CONFIGURATION
============================================================

Separate:

    Provider
    Endpoint
    Model

The model field must not be a fixed hardcoded dropdown for every provider.

Support:

    discovered models
    manually entered model IDs

UI:

    Model
    [Select discovered model ▼]
    [Refresh Models]

and:

    Enter model manually

If model discovery is unavailable:

    "Model discovery is not supported for this provider.
     Enter the model ID manually."

Do NOT make model discovery mandatory.

============================================================
PHASE 7 — CONNECTION TESTING
============================================================

Implement a real:

    Test Connection

button.

The test must verify:

1. Endpoint is reachable.
2. Authentication works if required.
3. Selected model exists/is usable if the provider exposes model
   information.
4. A minimal safe inference request works.

Do NOT send:

    candidate profile
    resume
    job description
    Q&A database
    personal information

during the connection test.

Use a minimal test prompt.

Example conceptual result:

    ✓ Connected
    Provider: Groq
    Model: xyz
    Latency: 842 ms
    Chat: Supported

or:

    ✕ Authentication failed

or:

    ✕ Model not found

or:

    ⚠ Endpoint reachable but model capability could not be verified

Do not simply mark a provider "Configured" because fields are populated.

Distinguish:

    Not configured
    Configured
    Testing
    Verified
    Failed
    Unknown

============================================================
PHASE 8 — ERROR NORMALIZATION
============================================================

Provider errors must not leak raw technical exceptions directly into the UI.

Normalize common failures:

    INVALID_API_KEY
    AUTHENTICATION_FAILED
    ENDPOINT_UNREACHABLE
    DNS_ERROR
    TIMEOUT
    MODEL_NOT_FOUND
    RATE_LIMITED
    QUOTA_EXCEEDED
    PROVIDER_UNAVAILABLE
    INVALID_REQUEST
    UNSUPPORTED_FEATURE
    CONTEXT_LENGTH_EXCEEDED
    CONTENT_POLICY
    UNKNOWN_PROVIDER_ERROR

Then show useful human-readable guidance.

Example:

    Authentication failed.

    Check that:
    • the API key is correct
    • the key has not expired
    • the endpoint belongs to the selected provider

    [Open API Key Guide]

Do not expose API keys in error messages or logs.

============================================================
PHASE 9 — API KEY SECURITY
============================================================

NEVER store provider API keys in:

    config.py
    profile.json
    plain-text settings
    logs
    database fields unless encrypted through the existing secret system

Use the existing:

    SecretsService

after auditing its current behavior.

The generic AI configuration should contain:

    provider_id
    endpoint
    model
    configuration metadata

The secret itself should be stored through SecretsService.

The AI UI must never place plaintext secrets into generic presentation
models or log messages.

When displaying credentials:

    API Key
    ••••••••••••••••

with:

    Show
    Hide
    Replace
    Clear

Do not show character count if that could reveal information about the
secret.

============================================================
PHASE 10 — PROVIDER SETUP CENTER
============================================================

The current UI shows:

    Ollama
    OpenAI
    Gemini
    DeepSeek

This is too provider-centric and will become difficult to maintain.

Create a better experience.

Possible UI:

    AI Provider

    ┌──────────────────────────────────────────────┐
    │ Provider                                     │
    │ [ Ollama ▼ ]                                 │
    │                                              │
    │ Protocol                                     │
    │ OpenAI Compatible                            │
    │                                              │
    │ Endpoint                                     │
    │ [ http://localhost:11434/v1 ]                │
    │                                              │
    │ API Key                                      │
    │ [ ••••••••••• ]                              │
    │                                              │
    │ Model                                        │
    │ [ llama3.1:8b ▼ ]                            │
    │                                              │
    │ [ Discover Models ] [ Test Connection ]      │
    └──────────────────────────────────────────────┘

Then:

    Need help setting this up?

    [Where to get API key]
    [Endpoint documentation]
    [Model documentation]
    [Setup tutorial]

The links must be provider-specific.

============================================================
PHASE 11 — "HOW DO I GET AN API KEY?" EXPERIENCE
============================================================

This is a major requirement.

A non-technical user should not have to search Google.

For every supported cloud provider provide:

    What is this?
    How to create an account
    How to create an API key
    Where to find the endpoint
    How to select a model
    Whether a payment method may be required
    Official documentation

Example:

    Groq

    1. Create/sign into your Groq account.
    2. Open the API key section.
    3. Create a key.
    4. Copy the key into JobPilot.
    5. Select a supported model.
    6. Test the connection.

    [Open Official API Documentation]
    [Open API Key Console]
    [View Setup Guide]

Do not write permanent provider instructions directly into random UI
widgets.

Store provider help metadata centrally.

============================================================
PHASE 12 — OFFICIAL DOCUMENTATION ONLY
============================================================

Provider documentation links must point to official sources whenever
possible.

Examples of the kind of official documentation currently available:

    Groq OpenAI Compatibility
    xAI API Documentation
    NVIDIA NIM API Documentation
    Hugging Face Inference Providers
    Ollama OpenAI Compatibility
    OpenRouter Developer Documentation

Do NOT link users to:

    random YouTube videos
    unofficial blogs
    affiliate websites
    scraped documentation

unless explicitly presented as optional community resources.

The provider registry should store:

    docs_url
    quickstart_url
    api_key_url
    models_url

Do not duplicate URLs throughout the application.

Before adding provider URLs, verify the current official documentation.

============================================================
PHASE 13 — TUTORIAL / SETUP GUIDE SYSTEM
============================================================

Build a reusable:

    ProviderSetupDialog

It should show:

    Provider
    Description
    Requirements
    Step-by-step setup
    Endpoint
    API key instructions
    Model instructions
    Test connection

Example:

    ┌─────────────────────────────────────────────┐
    │ Set up Groq                                │
    │                                             │
    │ Step 1                                      │
    │ Create your Groq account                    │
    │                                             │
    │ Step 2                                      │
    │ Create an API key                           │
    │                                             │
    │ Step 3                                      │
    │ Copy the key into JobPilot                  │
    │                                             │
    │ Step 4                                      │
    │ Choose a model                              │
    │                                             │
    │ Step 5                                      │
    │ Test connection                             │
    │                                             │
    │ [Official Documentation] [API Key Console]  │
    └─────────────────────────────────────────────┘

The setup guide must be generated from provider metadata.

============================================================
PHASE 14 — SUPPORT LOCAL + CLOUD EQUALLY
============================================================

Do not make cloud providers the primary path.

The UI should clearly support:

    Local
    Cloud
    Custom

Example:

    AI Provider

    Local
      Ollama
      Local OpenAI-Compatible Server

    Cloud
      Groq
      xAI
      NVIDIA
      Hugging Face
      OpenRouter
      OpenAI
      Gemini
      ...

    Custom
      OpenAI-Compatible Endpoint

The user should be able to use JobPilot completely locally if their
configured models support the required functionality.

Do not claim privacy/security guarantees that are not technically verified.

============================================================
PHASE 15 — FREE / LOW-COST MODEL DISCOVERY
============================================================

The user specifically wants accessible providers.

Create optional metadata:

    pricing_info_url

rather than hardcoding:

    "FREE"

or:

    "₹0"

because pricing and free limits change.

The UI can say:

    Pricing / usage limits may change.

    [Check Current Pricing]

Potentially categorize:

    Local
    Free tier available
    Paid
    Usage-based
    Unknown

But only when supported by current verified provider metadata.

Never promise unlimited free usage.

============================================================
PHASE 16 — AI FEATURE REQUIREMENTS
============================================================

Audit every JobPilot AI feature and define what it actually needs.

Create a capability matrix:

    Feature                    Requirement

    Q&A answering              Chat
    Job qualification          Chat / structured output
    Resume matching            Chat / structured output
    Screening                  Chat / structured output
    Job description extraction Chat
    Universal browser agent    Chat + structured output/tool capability
    Embeddings                 Embedding model
    Semantic search            Embeddings
    Vision                     Vision model if required

Do not assume one model is suitable for everything.

A provider can be configured for:

    Primary AI model

and eventually:

    Embedding model
    Vision model

if required.

But do not add unnecessary complexity until existing features require it.

============================================================
PHASE 17 — MODEL COMPATIBILITY CHECK
============================================================

A model being selectable does not mean it works with JobPilot.

Create a capability/compatibility test.

For example:

    Basic Chat Test
    Structured Output Test
    Streaming Test
    Tool Calling Test
    Vision Test
    Embedding Test

Only run tests relevant to the feature.

The user should be able to see:

    JobPilot Compatibility

    Chat                 ✓
    Structured Output    ✓
    Streaming            ✓
    Tool Calling         —
    Vision               ?
    Embeddings           —

This will prevent confusing provider configuration with application
compatibility.

============================================================
PHASE 18 — FALLBACK / MULTI-PROVIDER ARCHITECTURE
============================================================

Do not implement automatic fallback blindly.

First build:

    Primary Provider

Then design optional:

    Fallback Provider

Example:

    Primary:
        Ollama / llama3.1:8b

    Fallback:
        Groq / model-X

If the primary fails because of:

    timeout
    provider unavailable
    rate limit

the system may optionally use fallback.

BUT:

    authentication errors
    invalid requests
    unsupported capabilities

should not automatically retry forever.

Every fallback attempt must be logged safely.

This can be Phase 2 after the core provider architecture works.

============================================================
PHASE 19 — STREAMING
============================================================

Audit whether current Q&A/UI requires streaming.

If supported by the provider:

    token stream → UI

If unsupported:

    normal request → final response

The application must work without streaming.

Do not make streaming a hard requirement for provider compatibility.

============================================================
PHASE 20 — TIMEOUT / RETRY / RATE LIMIT POLICY
============================================================

Centralize network behavior.

Configuration should include:

    connect timeout
    request timeout
    max retries
    retry backoff

Retry only transient failures.

Do NOT blindly retry:

    401
    403
    invalid request
    model not found

Rate-limit handling should produce a useful UI message.

Example:

    Provider rate limit reached.

    Try again later or switch AI provider.

    [Switch Provider]

============================================================
PHASE 21 — PROVIDER CONFIGURATION STORAGE
============================================================

Inspect the existing settings architecture before changing database keys.

Do not break existing:

    ai.provider
    ai.model
    ai.api_url

or any existing configuration keys.

If necessary, introduce backward-compatible fields such as:

    ai.provider_type
    ai.provider_id
    ai.endpoint
    ai.model

but preserve compatibility with the current configuration.

Migration must be explicit.

Existing Ollama users must continue working without reconfiguration if
their current settings are valid.

============================================================
PHASE 22 — CURRENT OLLAMA CONFIGURATION MUST CONTINUE TO WORK
============================================================

The current UI already shows:

    Ollama
    llama3.1:8b
    http://localhost:11434/v1

Do not break this.

Existing Ollama users should experience:

    upgrade
    → application starts
    → existing Ollama configuration loads
    → Test Connection works
    → Q&A continues working

without manually rebuilding configuration.

============================================================
PHASE 23 — MODEL DISCOVERY
============================================================

Model discovery must be provider-specific.

Possible mechanisms:

    GET /models
    provider SDK
    provider-specific model endpoint
    Ollama model listing
    Hugging Face model/provider metadata

Do not assume every endpoint implements:

    GET /v1/models

correctly.

If discovery fails:

    do not treat provider as broken.

Show:

    "Automatic model discovery unavailable.
     Enter a model ID manually."

============================================================
PHASE 24 — CUSTOM ENDPOINT MODE
============================================================

Add:

    Custom OpenAI-Compatible

as a first-class provider.

Fields:

    Display Name
    Endpoint URL
    API Key
    Model
    Optional Organization
    Optional Headers

Security warning:

    "Only connect to endpoints you trust.
     Requests may contain job/application data depending on the feature."

Do not send credentials or user data to arbitrary endpoints without explicit
configuration.

============================================================
PHASE 25 — DATA PRIVACY / REQUEST PREVIEW
============================================================

Before using a cloud AI provider for candidate-related operations, the
system should know what data is being sent.

At minimum document internally:

    Job description
    Candidate profile
    Resume text
    Q&A data
    Application questions

depending on the feature.

The UI should make it clear that cloud providers may receive the data
required for the AI operation.

Do not claim that a provider does or does not retain data unless verified
from current official policy/documentation.

Local providers should be identified as local only when the endpoint is
actually local/configured as such.

============================================================
PHASE 26 — AI REQUEST CONTEXT BOUNDARY
============================================================

Do not let arbitrary provider configuration leak into business logic.

Architecture should look like:

    QnAService
         ↓
    AI Gateway
         ↓
    Provider Adapter
         ↓
    Endpoint

NOT:

    QnAService
         ↓
    OpenAI SDK directly

or:

    ScreeningService
         ↓
    Ollama directly

All AI calls should eventually pass through the common abstraction.

============================================================
PHASE 27 — OBSERVABILITY
============================================================

Add structured AI request telemetry.

Do NOT log:

    API key
    resume contents
    full candidate profile
    full Q&A
    sensitive application data

Safe metadata:

    provider_id
    model
    feature
    duration_ms
    success/failure
    normalized error
    retry count
    token usage if provider exposes it

This should integrate with existing LogService.

============================================================
PHASE 28 — SETTINGS UI REDESIGN
============================================================

The current UI is a good starting point, but redesign the AI section around
the user's actual workflow.

Current:

    Ollama
    OpenAI
    Gemini
    DeepSeek

Instead:

    AI Provider

    [Provider dropdown]

    Local
        Ollama

    Cloud
        Groq
        xAI
        NVIDIA
        Hugging Face
        OpenRouter
        OpenAI
        Gemini
        ...

    Custom
        OpenAI-Compatible

Then show only fields relevant to the selected provider.

Example:

    Groq

    Endpoint
    [https://.../v1]

    API Key
    [••••••••••••]

    Model
    [Select model ▼]

    [Discover Models]
    [Test Connection]

    ✓ Connected

    Need help?

    [Setup Guide]
    [API Documentation]
    [API Key]

============================================================
PHASE 29 — PROVIDER CARDS
============================================================

Do not create a giant list of provider cards.

Use cards only for quick selection if the UI remains compact.

The important information should be:

    Provider
    Local/Cloud
    Connection status
    Selected model

Example:

    Groq
    Cloud
    ✓ Connected
    llama-...

Keep the configuration panel focused.

============================================================
PHASE 30 — AI HEALTH STATUS
============================================================

The Settings header currently has:

    AI Configured

Improve this.

Distinguish:

    AI Not Configured
    AI Configured
    AI Verified
    AI Connection Failed
    AI Model Unavailable

Do not display:

    AI Configured

simply because a model name is present.

The status must come from actual configuration state.

============================================================
PHASE 31 — "AUTO CONFIGURE" SHOULD BE SAFE
============================================================

If provider detection is implemented, it must not silently overwrite
configuration.

For example:

    Ollama detected at localhost:11434

    [Use Ollama]

Then let the user confirm.

Likewise, if environment variables are detected:

    GROQ_API_KEY detected

do not automatically copy secrets into persistent settings without explicit
user action.

============================================================
PHASE 32 — TESTING
============================================================

Build provider tests using mocks/local fixtures.

Do NOT use real provider API calls in the normal test suite.

Test:

    Ollama adapter
    OpenAI-compatible adapter
    custom endpoint
    invalid endpoint
    invalid API key
    timeout
    model not found
    rate limit
    malformed response
    streaming
    structured output
    model discovery unavailable

Create a local fake OpenAI-compatible server for deterministic tests.

============================================================
PHASE 33 — REGRESSION TESTS
============================================================

Existing AI behavior must continue working.

Test:

    Q&A Engine
    job screening
    qualification
    resume matching
    existing Ollama flow
    existing OpenAI flow if present
    UniversalAIService
    Settings persistence
    SecretsService

Most importantly:

    Existing user configuration must continue working after migration.

============================================================
PHASE 34 — PROVIDER DOCUMENTATION REGISTRY
============================================================

Create a central provider metadata definition.

Conceptually:

    ProviderDefinition(
        id="groq",
        name="Groq",
        protocol="openai-compatible",
        default_endpoint="...",
        docs_url="...",
        quickstart_url="...",
        api_key_url="...",
        models_url="...",
        capabilities=[...]
    )

Do not hardcode provider URLs inside UI widgets.

When documentation changes, the registry should be the single place that
needs updating.

============================================================
PHASE 35 — DO NOT HARD-CODE PROVIDER PRICING
============================================================

Do not put:

    Free
    ₹0
    Unlimited
    100 requests/day

directly into code.

Instead store:

    pricing_url

and optionally:

    pricing_status = "check_current"

The UI should say:

    "Check current pricing and usage limits."

This prevents stale information.

============================================================
PHASE 36 — PROVIDER HELP SHOULD BE CONTEXTUAL
============================================================

If the user selects:

    Groq

show Groq setup instructions.

If:

    Ollama

show:

    Install Ollama
    Start Ollama
    Pull a model
    Verify local endpoint
    Select model

If:

    Custom endpoint

show:

    "Your provider must expose a compatible API."

Do not show irrelevant instructions.

============================================================
PHASE 37 — USER EXPERIENCE GOAL
============================================================

A non-technical user should be able to complete this flow:

    Open Settings
        ↓
    AI & Screening
        ↓
    Choose provider
        ↓
    Click "How to set up"
        ↓
    Follow official guide
        ↓
    Paste API key
        ↓
    Discover/select model
        ↓
    Test connection
        ↓
    See ✓ Verified
        ↓
    Save
        ↓
    Use Q&A / Screening / Job Evaluation

without needing to edit:

    config.py
    .env
    Python files
    source code

============================================================
PHASE 38 — IMPORTANT SECURITY BOUNDARY
============================================================

Do NOT implement:

    CAPTCHA bypass
    anti-bot bypass
    stealth browser behavior
    fingerprint spoofing
    rate-limit evasion

The AI service is an inference provider abstraction only.

It must not become a mechanism for bypassing platform security controls.

============================================================
PHASE 39 — IMPLEMENTATION ORDER
============================================================

Do not implement the entire feature at once.

Use these phases:

PHASE 0
Current AI architecture audit

PHASE 1
AI provider/domain contracts

PHASE 2
OpenAI-compatible adapter

PHASE 3
Ollama compatibility migration

PHASE 4
Provider registry

PHASE 5
Model discovery

PHASE 6
Connection testing + error normalization

PHASE 7
Secrets integration

PHASE 8
Provider setup/help metadata

PHASE 9
Settings UI redesign

PHASE 10
Migrate QnAService / Screening / AI features to gateway

PHASE 11
Custom OpenAI-compatible endpoint

PHASE 12
Provider capability detection

PHASE 13
Streaming / structured output where supported

PHASE 14
Telemetry / diagnostics

PHASE 15
Fallback provider architecture

PHASE 16
Full regression testing

PHASE 17
Production hardening

============================================================
PHASE 40 — ACCEPTANCE CRITERIA
============================================================

The feature is NOT complete until all of the following work.

1.

Existing Ollama configuration:

    llama3.1:8b
    http://localhost:11434/v1

continues working.

2.

A generic OpenAI-compatible endpoint can be configured without adding
source code.

3.

A user can configure a cloud provider using:

    endpoint
    API key
    model

4.

Model discovery works where supported.

5.

Manual model entry works when discovery is unavailable.

6.

Test Connection distinguishes:

    configured
    verified
    failed
    unavailable

7.

API keys are never written to logs.

8.

API keys are stored using the existing secure secret mechanism.

9.

Q&A works through the common AI gateway.

10.

AI provider can be changed without changing Q&A/business logic.

11.

Provider-specific documentation/help is available from the UI.

12.

Official documentation links are used.

13.

No pricing/free-tier claim is hardcoded.

14.

Custom OpenAI-compatible endpoints work.

15.

A provider that does not support a requested capability produces a clear
message instead of a cryptic exception.

16.

Existing tests remain green.

17.

No existing LinkedIn/Naukri automation is changed.

============================================================
FINAL DELIVERABLE
============================================================

Before writing implementation code, provide:

1. Current AI architecture audit
2. Current AI provider dependencies
3. Existing configuration keys
4. Existing SecretsService integration
5. Existing AI feature dependency matrix
6. Proposed AI Gateway architecture
7. Provider Adapter architecture
8. OpenAI-compatible endpoint design
9. Provider registry design
10. Capability model
11. Model discovery strategy
12. Connection test strategy
13. Error normalization strategy
14. Secret storage strategy
15. Provider documentation/help system
16. Settings UI changes
17. Migration strategy preserving Ollama
18. Test strategy
19. Complete phase-by-phase implementation plan
20. Files to add/modify
21. Risks and compatibility concerns

Then STOP.

Do not implement code until I explicitly approve the revised plan.

The final architectural principle is:

    JobPilot does NOT depend on OpenAI.

    JobPilot depends on an AI ABSTRACTION.

        JobPilot AI Features
                 ↓
             AI Gateway
                 ↓
          Provider Adapter
             ↙       ↘
    Native Provider   OpenAI-Compatible
                         ↓
               Any compatible endpoint

The user should be able to change:

    provider
    endpoint
    API key
    model

without changing JobPilot's AI business logic.