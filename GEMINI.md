## graphify & Token-Efficient Exploration

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules for AI Agents:
- **Never read entire files line-by-line blindly:** In this large codebase (>750 files), reading full files exhausts context and wastes tokens. Use targeted line ranges (`StartLine`/`EndLine`) and focused `grep -n` definitions.
- **Graph-First Exploration:** For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- **After modifying code**, run `graphify update .` to keep the graph current (AST-only, no API cost).
- For complete token-preservation invariants, see `.agents/rules/token-efficient-exploration.md`.

## Anti-AI Slop & Production Code Standards
- **Zero Emojis in Code & Logs:** Never use emojis or icons in source code, variable names, docstrings, inline comments, or log messages (e.g. 🚀, ✅, ⚠️, ❌). Use professional structured logging.
- **No Performative Comments:** Do not write chatty or syntax-restating comments (`# Loop through items`). Comments explain *why*, not *what*.
- **No Mock Stubs:** Never leave incomplete placeholders (`# TODO: implement later` or dummy returns). All code must be complete, testable, and production-ready.
- Full details: `.agents/rules/code-standards-and-anti-slop.md`.
