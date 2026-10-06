# Feature Development Template — JobPilot
*Copy and fill out this document for every new feature before implementing code.*
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §6, §17*

---

# Feature: [Feature Name / Title]

## 1. Requirement & Purpose
- **Goal:** [Clear 1-2 sentence description of what the feature achieves]
- **User Value:** [Why this feature is needed and who uses it]
- **Scope Limits:** [Explicitly what this feature will NOT do]

## 2. Existing Implementation & Audit
- **Related Services:** [Existing services in app/services/ to reuse or extend]
- **Related Repositories:** [Existing repositories in app/repositories/]
- **Related UI Views:** [Existing views in app/ui/views/]
- **Related Automation Engines:** [Existing platform engines in platforms/]
- **Existing Tests:** [Tests currently covering this area]

## 3. Architecture Impact & Layer Boundaries
- **UI Layer (`app/ui/`):** [What changes? E.g. new component, updated view, new signal connection]
- **Service Layer (`app/services/`):** [What business logic is added? What DTOs are introduced?]
- **Repository Layer (`app/repositories/`):** [What database queries are needed?]
- **Database Layer (`app/db/models/`):** [Any new tables or nullable columns? Default values?]
- **Automation Layer (`platforms/`):** [Any worker or browser interaction changes?]

## 4. Data Flow & Sequence Diagram
```
[User Action in UI]
       │
       ▼
[Service Method Invoked]
       │
       ▼
[Repository Query / Worker Spawned]
       │
       ▼
[Database Persistence / Browser Action]
       │
       ▼
[Signal Emitted -> UI Updated]
```

## 5. State Machine & Lifecycle Transitions
- **Initial State:** [e.g. IDLE]
- **Intermediate States:** [e.g. INITIALIZING -> PROCESSING -> PENDING_REVIEW]
- **Terminal States:** [e.g. COMPLETED / FAILED_UNRECOVERABLE]
- **Intervention Triggers:** [What triggers PAUSED_FOR_INTERVENTION?]

## 6. Files Affected
- `app/...`: [Description of change]
- `tests/...`: [New or updated tests]
- `docs/...`: [Documentation updates]

## 7. Implementation Plan (Smallest Safe Change)
1. Step 1: [Audit existing callers and run baseline tests]
2. Step 2: [Add/update Repository methods if persistence is required]
3. Step 3: [Implement Service logic and DTO conversions]
4. Step 4: [Connect UI signals and widgets using ThemeManager]
5. Step 5: [Write unit and integration tests]

## 8. Error Cases & Edge Conditions
| Failure Scenario | Detection Mechanism | System Reaction | User Presentation |
|---|---|---|---|
| Invalid Input | Pydantic / Schema check | Raise ValidationError | Show validation error banner |
| Timeout | Explicit wait exceeded | Transition to FAILED | Log error and offer retry |
| Session Expired | Redirect to login | Set LOGIN_WALL | Request manual login |

## 9. Recovery & Fallback Behavior
- **Automatic Recovery:** [How does the system attempt to recover?]
- **Manual Fallback:** [When is control handed back to the user?]

## 10. Test Strategy
- **Baseline Test Suite:** [Command to run existing tests]
- **New Unit Tests:** [Specific test methods and files to create]
- **Edge Case Tests:** [Mocked failure and boundary tests]
- **UI Offscreen Test:** `.venv/bin/python run_desktop.py --offscreen --test-run`

## 11. Verification Plan
- [ ] Syntax check: `python -m py_compile ...`
- [ ] Baseline tests executed and recorded
- [ ] New tests passing
- [ ] Zero regressions across existing test suite
- [ ] Theme parity verified (Dark & Light modes)

## 12. Documentation Updates
- [ ] Updated `docs/current_architecture.md` (if layer interfaces changed)
- [ ] Updated `WorkingFlow/` document (if automation flow changed)

## 13. Risks & Known Limitations
- **Risk 1:** [Potential side-effect or constraint]
- **Mitigation:** [How this risk is minimized or monitored]

## 14. Mandatory Feature Completion Checklist
- [ ] Requirements understood
- [ ] Existing implementation inspected
- [ ] Architecture identified
- [ ] Plan created
- [ ] Implementation completed
- [ ] Error handling implemented
- [ ] Edge cases considered
- [ ] Tests added/updated
- [ ] Targeted tests passed
- [ ] Regression tests passed
- [ ] UI verified if applicable
- [ ] Documentation updated
- [ ] No secrets exposed
- [ ] No unrelated changes
- [ ] Known limitations documented
