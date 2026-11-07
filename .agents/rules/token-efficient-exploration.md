# Token-Efficient Codebase Navigation & Exploration Rules

> **MANDATORY CONTEXT & TOKEN PRESERVATION DIRECTIVE:**
> JobPilot is a large-scale enterprise codebase (>750 files, 1.1M+ words, 11,000+ AST nodes).
> Agents that read files line-by-line, dump massive terminal outputs, or scan folders blindly
> waste tens of thousands of tokens, bloat context windows, slow down response latency, and risk hallucination.
>
> All AI agents working in this repository **MUST** follow this token-efficient protocol.

---

## 1. The 4-Tier Navigation Hierarchy (Graph-First)

Before reading any file or making code edits, agents must navigate using the most token-efficient tier available:

```
TIER 1: Graph Query (Fewest tokens) ──► graphify explain / path / query
        │
TIER 2: Targeted Index / Arch Docs ──► docs/current_architecture.md, GRAPH_REPORT.md
        │
TIER 3: Focused Line-Numbered Grep ──► grep -n / git grep (restricted to 10-30 lines)
        │
TIER 4: Bounded Range Read          ──► read_file with StartLine / EndLine ONLY
```

---

## 2. Hard Invariants for Codebase Exploration

### ❌ Strictly Prohibited (Token Traps):
1. **NO Blind Full-File Reads:** Never call `read_file` on entire files exceeding 100 lines unless performing a verified complete file overhaul.
2. **NO Unbounded Terminal Dumps:** Never execute commands that dump hundreds or thousands of lines to stdout (e.g. raw `find .`, `grep -r`, `cat`, or unfiltered database/json dumps). Always pipe through `head -n 30`, `tail -n 30`, `grep`, or `jq`.
3. **NO Sequential File Crawling:** Never iterate through multiple source files one by one trying to understand where a function is called or defined.
4. **NO Manual Dependency Tracing:** Never manually hunt through imports across multiple directories when `graphify path` can compute the exact relationship in one call.

### ✅ Mandatory Best Practices:
1. **Use `graphify explain "<concept>"` First:**
   - To inspect any class, service, method, or subsystem (e.g. `WorkdayAccountService`, `UniversalApplicationOrchestrator`, `FieldMapper`), run:
     ```bash
     .venv/bin/python -m graphify explain "<concept>"
     ```
   - This instantly returns the exact source file, line number, degree, callers, and dependencies using zero LLM tokens.
2. **Use `graphify path "<A>" "<B>"` for Cross-Module Relationships:**
   - When tracing how Component A interacts with Component B:
     ```bash
     .venv/bin/python -m graphify path "<ComponentA>" "<ComponentB>"
     ```
3. **Use Scoped Line Range Reads:**
   - Once the exact line number is known from Tier 1 or Tier 3, read only the target method and immediate context (typically 30–60 lines):
     - Example: `read_file(Path="app/services/workday_account_service.py", StartLine=70, EndLine=120)`
4. **Use Line-Numbered Grep for Symbols:**
   - When looking up definitions:
     ```bash
     grep -nE "^(class|def) <symbol_name>" app/services/*.py
     ```
5. **Post-Edit AST Synchronization:**
   - After completing code modifications, run `.venv/bin/python -m graphify update .` to keep the knowledge graph synchronized at zero LLM cost.

---

## 3. Workflow Comparison: Bad vs. Token-Efficient

| Task | ❌ Token-Wasteful Pattern (15,000+ tokens) | ✅ Token-Efficient Pattern (< 800 tokens) |
| :--- | :--- | :--- |
| **Find where a service is used** | `read_file` on 5 different service files line-by-line | `.venv/bin/python -m graphify explain "ServiceName"` |
| **Understand connection between UI and DB** | Read view, controller, service, and repo files | `.venv/bin/python -m graphify path "CredentialsSection" "SettingsRepository"` |
| **Modify a single method in a 700-line file** | Read lines 1–700 of `form_filler.py` | `grep -n "def target_method"` then read lines 240–280 |
| **Check architecture overview** | Read multiple READMEs and source directories | Check `graphify-out/GRAPH_REPORT.md` God Nodes & Communities |

---

## 4. Phase 1 (Audit) Integration

During **Phase 1: AUDIT** of the standard 8-phase workflow:
- The agent must state the specific target files and line ranges identified via Graphify or targeted grep *before* invoking `read_file` or `edit_file`.
- Never load more than 2 full files into context in a single turn.

