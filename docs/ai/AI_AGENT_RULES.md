# JobPilot — AI & LLM Engine Rules
**Specialized Guidelines for Multi-Tier QnA, Semantic Answering, and AI Boundaries**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §10*

---

## 1. AI Integration Philosophy

Artificial Intelligence and Large Language Models (LLMs) in JobPilot must serve as an **interpretive layer**, not an uncontrolled replacement for deterministic logic.

### Core Principles:
1. **Deterministic Logic First:** If a question or field can be answered using rules, regex, or static profile matching, never call an LLM.
2. **Zero Hallucination:** An LLM must NEVER fabricate candidate skills, years of experience, citizenship status, certifications, or compensation requirements.
3. **Factual Provenance:** Every piece of candidate data supplied to an employer must be traceable to a verified fact source.
4. **Cooperative Fallback:** If an answer cannot be determined with certainty, trigger `InterventionReason.UNKNOWN_QUESTION` rather than guessing.

---

## 2. Multi-Tier Question Answering Architecture

The QnA Engine (`modules/qna_engine.py` and `app/services/qna_service.py`) processes screening questions through a strict three-tier priority pipeline:

```
┌────────────────────────────────────────────────────────┐
│               INCOMING SCREENING QUESTION              │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│              TIER 1: DETERMINISTIC RULES               │
│   Exact match against config/questions.py & DB rules.  │
│   Work authorization, notice period, CTC, visa status. │
└───────────────────────────┬────────────────────────────┘
                            │ (No match found)
┌───────────────────────────▼────────────────────────────┐
│              TIER 2: RESUME FACT EXTRACTION            │
│   Keyword & semantic lookup against verified facts     │
│   in ProfileService and ResumeService.                 │
└───────────────────────────┬────────────────────────────┘
                            │ (Ambiguous or descriptive question)
┌───────────────────────────▼────────────────────────────┐
│              TIER 3: BOUNDED LLM INFERENCE             │
│   Structured prompt with strict factual context.       │
│   Ollama (local) or OpenAI/Gemini (cloud).             │
└───────────────────────────┬────────────────────────────┘
                            │ (Low confidence or missing fact)
┌───────────────────────────▼────────────────────────────┐
│               FALLBACK: MANUAL INTERVENTION            │
│   Pause application; prompt user to answer; save rule  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Factual Provenance Requirements

Whenever the QnA engine outputs an answer, it must record a `provenance` metadata tag:

| Provenance Tag | Source | Trust Level |
|---|---|---|
| `QNA_RULE` | Explicit mapping in `config/questions.py` or user QnA database. | Absolute (100%) |
| `PROFILE_FACT` | Structured field in `config/profile.json` (e.g. phone, address, LinkedIn URL). | Absolute (100%) |
| `RESUME_FACT` | Directly extracted text or metric from user's verified resume PDF. | High (95%) |
| `USER_MANUAL_INPUT` | Value typed by user during a live intervention pause. | Absolute (100%) |
| `LLM_SYNTHESIS` | Formatted summary synthesized by LLM from verified resume facts. | Medium (Requires validation) |

Any answer lacking verifiable provenance is **STRICTLY PROHIBITED** from automated submission.

---

## 4. LLM Prompt Engineering & Output Validation

When Tier 3 LLM inference is required:
1. **Context Bounding:**
   - Supply only the question, field constraints (min/max length, number, radio options), and verified candidate facts.
   - **Never** include unrelated sensitive credentials (API keys, account passwords, session cookies).
2. **Deterministic Hyperparameters:**
   - Temperature: `0.0` to `0.2` (minimize creativity/hallucination).
   - Maximum Output Tokens: Bounded to field requirements (e.g. 50 tokens for short text, 200 for essays).
3. **Structured Output (JSON Only):**
   - All LLM queries must request strict JSON responses conforming to a schema:
   ```json
   {
     "answer": "5",
     "confidence": 0.95,
     "provenance_source": "RESUME_FACT:skills.python.years",
     "reasoning": "Candidate worked 5 years in Python across Company A and B."
   }
   ```
4. **Schema Validation:**
   - Validate JSON using Pydantic or `jsonschema`.
   - If parsing fails or confidence is below threshold (< 0.8), route to `InterventionReason.UNKNOWN_QUESTION`.

---

## 5. Local vs Cloud LLM Privacy

1. **Local LLM Preference:**
   - Prefer local inference via Ollama (`llama3`, `mistral`, `qwen2.5`) when configured to ensure candidate privacy and zero API costs.
2. **Cloud LLM Usage (OpenAI / Gemini):**
   - Permitted only when the user explicitly provides an API key in `config/secrets.py`.
   - Keys must never be hardcoded or checked into Git.
