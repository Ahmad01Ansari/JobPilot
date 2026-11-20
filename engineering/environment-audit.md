# JobPilot AI Engineering Environment Audit & Readiness Assessment

**Date:** 2026-11-20  
**Target Environment:** Antigravity IDE / Desktop Assistant  
**Repository:** `/home/ahmad10raza/Documents/Mastering/JobPilot`  
**Auditor:** Senior AI Development Environment Engineer & Antigravity Configuration Specialist  
**Status:** Phase 1 Complete (Read-Only Inspection)

---

## 1. Executive Summary

This audit assesses the current Antigravity configuration, local tooling, Python virtual environment, installed skills, active rules, and MCP servers across both user-level (`~/.gemini/`, `~/.agents/`) and workspace-level (`/home/ahmad10raza/Documents/Mastering/JobPilot/`) scopes.

The JobPilot application is an advanced beta-stage multi-platform job automation desktop application built with PySide6, Selenium, SQLite (WAL mode), Flask, and a multi-provider AI Gateway (Ollama, Gemini, OpenAI, Claude, DeepSeek).

**Audit Outcome:**
The environment has strong foundational components (working Python 3.11 runtime, Git 2.55.0, Ollama 0.34.2, Playwright 1.49.1, Node 24.21.0, and an extensive suite of 38+ workspace skills). However, specialist engineering agents, project-scoped MCP servers (Filesystem MCP, Playwright MCP, Graphify MCP), and specific static analysis tools (`ruff`, `bandit`) are missing or unconfigured.

---

## 2. Environment Inventory

### 2.1 Configuration File Discovery & Locations

| Scope | Location | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Workspace Rules** | `AGENTS.md` | Active (23,018 bytes) | Primary project constitution (30 security rules, 32 OS invariants). Near the 24 KB per-file budget cap. |
| **Workspace Graphify** | `GEMINI.md` | Active (1,438 bytes) | Contextual graphify navigation & anti-slop guidelines. |
| **Workspace Rules Dir** | `.agents/rules/` | Partially populated | Contains `code-standards-and-anti-slop.md`, `cross-platform-rules.md`, `graphify.md`, `token-efficient-exploration.md`. Four 0-byte placeholders exist (`architecture.md`, `python-standards.md`, `security-policy.md`, `testing-policy.md`). |
| **Workspace Settings** | `.gemini/settings.json` | Active | Configures `BeforeTool` hook guarding `read_file` and `list_directory` via `graphify hook-guard gemini`. |
| **VS Code / IDE** | `.vscode/settings.json` | Active | Points Python interpreter to `${workspaceFolder}/.venv/bin/python`. |
| **Global Settings** | `~/.gemini/config/config.json` | Active | Plugin configuration, user settings, permission grants. |
| **Global MCP Config** | `~/.gemini/antigravity/mcp_config.json` | Active | Configured with `n8n-mcp` (Streamable HTTP on `http://localhost:5678/mcp-server/http`). |
| **Global MCP Config (Alt)** | `~/.gemini/config/mcp_config.json` | Present (0 bytes) | Empty file; needs safe preservation/reconciliation. |
| **User Agents** | `~/.agents/` | Active | Global skills (`base44-*`, `graphify`, `find-skills`), rule `graphify.md`. |
| **User Skills** | `~/.gemini/antigravity/skills/` | Active | 15 n8n workflow engineering skills. |

---

### 2.2 Existing Specialist Agents

| Agent Name | Scope / Source | Current State | Responsibilities |
| :--- | :--- | :--- | :--- |
| `self` | Antigravity Builtin | Available | Full parent capabilities clone. |
| `research` | Antigravity Builtin | Available | Read-only codebase and web search exploration. |
| `browser` | Antigravity Builtin | Available | Chrome DevTools live browser interaction. |
| `image-generator`| Antigravity Builtin | Available | Image generation and visual mockups. |
| `architect.md` | `.agents/agents/` | 0 bytes (Empty) | Untracked placeholder, no prompt or configuration. |
| `python-developer.md` | `.agents/agents/` | 0 bytes (Empty) | Untracked placeholder, no prompt or configuration. |
| `qa-engineer.md` | `.agents/agents/` | 0 bytes (Empty) | Untracked placeholder, no prompt or configuration. |
| `code-reviewer.md` | `.agents/agents/` | 0 bytes (Empty) | Untracked placeholder, no prompt or configuration. |

**Assessment:**  
No dedicated, fully configured JobPilot specialist agents currently exist. The 0-byte placeholders in `.agents/agents/` must be populated or structured into supported Antigravity subagents following the official `subagent: true`, `mainAgent: false` frontmatter schema.

---

### 2.3 Existing Skills

#### A. Built-in Skills (10)
- `agy-customizations`: Comprehensive guide to Antigravity Customization System.
- `antigravity-guide`: Reference manual for IDE, CLI, and configuration.
- `automation`: Background task scheduler and runner.
- `generative_ui`: Interactive HTML/React widgets and diagrams.
- `migrate-agent-settings`: Cross-agent config migration.
- `migrate-workflows`: Workflow-to-skill converter.
- `plugin`: Plugin packaging and lifecycle manager.
- `run-workflow`: Python orchestration runner (`agent`, `parallel`, `pipeline`).
- `swarm_monitor`: Swarm stall detector.
- `ui-plugin-navigation`: UI panel integration shortcuts.

#### B. Installed Plugins (3)
1. **`linkedin-skills`** (12 skills):
   `linkedin-comment-drafter`, `linkedin-content-planner`, `linkedin-employee-advocacy`, `linkedin-engager-analytics`, `linkedin-hook-extractor`, `linkedin-humanizer`, `linkedin-interviewer`, `linkedin-post-writer`, `linkedin-profile-optimizer`, `linkedin-reply-handler`, `linkedin-repurposer`, `linkedin-thread-monitor`.
2. **`logo-design`** (1 skill):
   `logo-design`.
3. **`modern-web-guidance-plugin`** (2 skills):
   `chrome-extensions`, `modern-web-guidance`.

#### C. Workspace Skills (`.agents/skills/`) (38 populated + 5 placeholders)
- **Active / Populated:**
  `banner-design`, `brand`, `building-lit-components`, `building-static-site-rss-feeds`, `building-templ-components`, `checking-wsh-vrt`, `code-to-prd`, `committing-code`, `creating-agent-skills`, `creating-test-cases`, `deploying-with-isucon-ansible`, `design`, `design-system`, `designing-isucon-architecture`, `frontend-design`, `graphify`, `operating-isucon-servers-via-ssh`, `planning-wsh-improvements`, `porting-isucon-rust-to-go`, `releasing-zig-with-goreleaser`, `run-bot`, `running-isucon-as-an-agent`, `sharing-sockets-with-so-reuseport-in-zig`, `slides`, `tuning-isucon-linux-and-nginx`, `ui-styling`, `ui-ux-pro-max`, `unslop`, `using-go-tool-directive`, `using-grafana-mcp`, `using-unocss-with-templ`, `winning-isucon`, `winning-web-speed-hackathon`, `writing-feature-spec`, `writing-implementation-tasks`, `writing-isucon-arch-subagent-tasks`, `writing-project-constitution`, `writing-technical-design`, `writing-zig-cli-tools`.
- **Empty Placeholders (Created recently, 0-byte or empty):**
  `understand-codebase/SKILL.md` (0 bytes), `implement-feature/` (empty dir), `debug-regression/` (empty dir), `review-changes/` (empty dir), `release-check/` (empty dir).

---

### 2.4 Existing Rules

1. **`AGENTS.md` (Workspace Root):**
   - Size: 23,018 bytes.
   - Mandates: 8-phase development lifecycle, PySide6 thread isolation, SQLite WAL mode, zero fake data, no `except: pass`, explicit user permission for git commit/push, 30 defensive security rules, 32 desktop OS compatibility rules, token-efficient navigation.
2. **`GEMINI.md` (Workspace Root):**
   - Rules for `graphify` navigation and zero AI slop / emojis in code and logs.
3. **`.agents/rules/`:**
   - `code-standards-and-anti-slop.md` (5,820 bytes)
   - `cross-platform-rules.md` (5,813 bytes)
   - `graphify.md` (795 bytes)
   - `token-efficient-exploration.md` (4,279 bytes)
   - 0-byte placeholders: `architecture.md`, `python-standards.md`, `security-policy.md`, `testing-policy.md`.
4. **`~/.agents/rules/graphify.md` (Global):**
   - Fallback rules for graphify navigation across repositories.
5. **`~/.gemini/config/plugins/linkedin-skills/rules/AGENTS.md` (Global Plugin):**
   - Specific conventions for LinkedIn marketing automation skills.

---

### 2.5 MCP Servers

| MCP Server | Config Location | Status | Type | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `n8n-mcp` | `~/.gemini/antigravity/mcp_config.json` | Active | Streamable HTTP (`localhost:5678`) | Workflow orchestration tools. |
| `Filesystem MCP` | None | **Missing** | Stdio (`@modelcontextprotocol/server-filesystem`) | Direct project file inspection. |
| `Playwright MCP` | None | **Missing** | Stdio (`@executeautomation/playwright-mcp-server` or equivalent) | Live browser UI testing & debugging. |
| `Graphify MCP` | Exists locally (`.venv/bin/graphify-mcp`) | **Unregistered** | Stdio | Fast AST-based knowledge graph querying. |
| `Git MCP` | None | **Not Recommended** | N/A | Git CLI 2.55.0 already provides full functionality via `run_command`. |

---

### 2.6 Local Development Tools

| Tool | Requested | System Path / Version | Project `.venv` Status | Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | Yes | `/home/ahmad10raza/anaconda3/bin/python3` (3.12.7) | `.venv/bin/python` (**3.11.16**) | Installed & active in `.venv`. Compatible with PySide6 & JobPilot dependencies. |
| **pytest** | Yes | `/home/ahmad10raza/anaconda3/bin/pytest` (7.4.4) | Not installed in `.venv` | **Missing in `.venv`**. Note: JobPilot currently executes tests via standard library `unittest`. |
| **pytest-cov**| Yes | Not installed | Not installed in `.venv` | **Missing**. |
| **Ruff** | Yes | Not installed | Not installed in `.venv` | **Missing**. High-speed linter/formatter recommended for Python engineering. |
| **Bandit** | Yes | Not installed | Not installed in `.venv` | **Missing**. Security AST scanner recommended for automated security checks. |
| **Playwright**| Yes | CLI not installed globally | Python `playwright 1.49.1` installed in `.venv` | Python library ready; Node / MCP runner available via `npx`. |
| **Git** | Yes | `/usr/bin/git` (**2.55.0**) | N/A | Installed and fully functional. |
| **Ollama** | Yes | `/usr/local/bin/ollama` (**0.34.2**) | N/A | Installed with local models: `qwen3.5:9b`, `llama3.1:8b`, `nomic-embed-text`, `llama3`. |
| **Node / NPX**| Supporting | `/usr/bin/node` (**v24.21.0**), `npx` (**11.19.0**) | N/A | Available to run Stdio MCP servers without global package pollution. |

---

## 3. Analysis of Capabilities & Gaps

### 3.1 Missing Capabilities
1. **Specialist Engineering Subagents:**
   No dedicated subagents exist for:
   - System architecture and dependency analysis (`jobpilot-architect`).
   - Python & PySide6 development adhering to JobPilot's concurrency invariants (`jobpilot-python-developer`).
   - Automated and regression testing adhering to JobPilot's test suite (`jobpilot-qa-engineer`).
   - Independent, adversarial code review for security and anti-slop checks (`jobpilot-code-reviewer`).
2. **Project-Scoped Filesystem MCP:**
   Filesystem access via MCP restricted strictly to `/home/ahmad10raza/Documents/Mastering/JobPilot`.
3. **Playwright MCP Server:**
   Allows live browser DOM inspection, selector validation, and UI test execution via MCP.
4. **Graphify MCP Server:**
   JobPilot already generated `graphify-out/` and has `.venv/bin/graphify-mcp` installed. Wiring it as a Stdio MCP server allows instant graph querying (`query_graph`, `get_node`, `shortest_path`) directly within Antigravity without spawning CLI subshells.
5. **Standardized Reusable Skills:**
   Missing production-ready skills for:
   - `codebase-investigation`
   - `feature-implementation`
   - `regression-debugging`
   - `independent-code-review`
   - `release-validation`
6. **Code Quality Tools in `.venv`:**
   `ruff` and `bandit` are missing from `.venv`, preventing automated linting and security scanning.

### 3.2 Duplicate Capabilities
1. **MCP Configuration Files:**
   `~/.gemini/antigravity/mcp_config.json` (active, contains `n8n-mcp`) vs `~/.gemini/config/mcp_config.json` (0 bytes). To avoid shadowing or split-brain configurations, new servers should be safely merged into `~/.gemini/antigravity/mcp_config.json` while preserving `n8n-mcp`.
2. **Empty Placeholders:**
   Recently added 0-byte files in `.agents/agents/` and `.agents/rules/` duplicate the roles of the proposed `jobpilot-*` agents and rules. These should be cleanly replaced or populated during Phase 2.
3. **Git MCP vs Git CLI:**
   Installing a Git MCP server is redundant; Antigravity already has full access to `git` 2.55.0 via `run_command`.

### 3.3 Potential Configuration Conflicts & Risks
1. **`.venv/bin/pip` Interpreter Path:**
   `.venv/bin/pip` has a hardcoded shebang referencing `/home/ahmad10raza/Documents/Mastering/JobPilot/.venv_local/bin/python3.11` (which does not exist). Running `.venv/bin/pip` directly fails with `bad interpreter`. However, running `.venv/bin/python -m pip` works properly. **Resolution:** Use `.venv/bin/python -m pip` for all pip operations.
2. **Rule Budget Limits:**
   Antigravity enforces a strict 24,000-byte cap per rule file and a 20,000-token aggregate rules budget. `AGENTS.md` is currently at 23,018 bytes (~96% capacity). **Resolution:** Do NOT add more text to `AGENTS.md`. All new agent-specific guidelines must reside in modular agent files (`.agents/agents/<name>.md`) or skills.
3. **Security Constitution Compliance:**
   `AGENTS.md` strictly prohibits automated CAPTCHA solving, stealth evasion, unvalidated URL navigation, and committing code without explicit user permission. All new specialist agents must embed these invariants into their system prompts.

---

## 4. Proposed Phase 2 Implementation Plan

Upon human approval, Phase 2 will execute the following safe, non-destructive setup:

### Step 1: Safe MCP Server Configuration
Merge into `~/.gemini/antigravity/mcp_config.json` (preserving existing `n8n-mcp`):
1. **`filesystem`**:
   - Command: `npx`
   - Args: `["-y", "@modelcontextprotocol/server-filesystem", "/home/ahmad10raza/Documents/Mastering/JobPilot"]`
   - Restriction: Strictly scoped to the JobPilot workspace directory.
2. **`playwright`**:
   - Command: `npx`
   - Args: `["-y", "@executeautomation/playwright-mcp-server"]`
   - Runs locally on demand.
3. **`graphify`**:
   - Command: `/home/ahmad10raza/Documents/Mastering/JobPilot/.venv/bin/graphify-mcp`
   - Args: `[]`
   - Working Directory: `/home/ahmad10raza/Documents/Mastering/JobPilot`
   - Runs locally, uses existing `graphify-out/`.

### Step 2: Create Specialist Antigravity Agents
Create structured Markdown agent definitions in `.agents/agents/`:
1. **`jobpilot-architect.md`**:
   - Responsibility: Architecture analysis, module dependencies, concurrency invariants (Qt thread isolation, SQLite WAL), and change planning.
   - Tools: Read-only codebase inspection, graphify MCP, filesystem MCP.
2. **`jobpilot-python-developer.md`**:
   - Responsibility: Python 3.11 implementation, PySide6 UI development, service refactoring, defensive coding, strict type hints, zero fake data, no `except: pass`.
   - Tools: File read/write/edit, execution in `.venv`, git branch operations.
3. **`jobpilot-qa-engineer.md`**:
   - Responsibility: Test design, unit test execution (`.venv/bin/python -m unittest discover -s tests`), regression testing, headless GUI verification (`run_desktop.py --offscreen --test-run`), Playwright UI validation.
   - Tools: Run test commands, Playwright MCP, read logs.
4. **`jobpilot-code-reviewer.md`**:
   - Responsibility: Independent diff verification, compliance with `AGENTS.md` (30 security rules, 32 OS rules), anti-slop verification (zero emojis, production code comments), branch review.
   - Tools: Git diff inspection, read files.

### Step 3: Create Reusable Engineering Skills
Populate the missing skills in `.agents/skills/`:
1. `.agents/skills/codebase-investigation/SKILL.md`
2. `.agents/skills/feature-implementation/SKILL.md`
3. `.agents/skills/regression-debugging/SKILL.md`
4. `.agents/skills/independent-code-review/SKILL.md`
5. `.agents/skills/release-validation/SKILL.md`

### Step 4: Install Missing Local Dev Tools (Optional / Requires Approval)
With user approval, install `ruff` and `bandit` into `.venv`:
```bash
.venv/bin/python -m pip install ruff bandit pytest pytest-cov
```
*(No system-wide packages or Python runtime versions will be altered.)*

### Step 5: Generate Architecture Reference Documentation
Generate the three requested evidence-backed architecture documents:
1. `engineering/architecture/SYSTEM_OVERVIEW.md`
2. `engineering/architecture/MODULE_DEPENDENCIES.md`
3. `engineering/architecture/CRITICAL_MODULES.md`

---

## 5. Required Human Approvals Before Phase 2

Before executing Phase 2, please confirm:
1. Approval to update `~/.gemini/antigravity/mcp_config.json` by adding `filesystem`, `playwright`, and `graphify` entries alongside `n8n-mcp`.
2. Approval to replace the empty 0-byte placeholders in `.agents/agents/` and `.agents/skills/` with the formal `jobpilot-*` agents and skills.
3. Approval to install `ruff`, `bandit`, `pytest`, `pytest-cov` inside `.venv` via `.venv/bin/python -m pip install`.
4. Approval to generate the architectural reference reports in `engineering/architecture/`.

