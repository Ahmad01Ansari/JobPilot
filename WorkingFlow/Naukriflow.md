You are working on the existing JobPilot Naukri automation.

IMPORTANT:
The existing Naukri automation is partially working:
- Job discovery/search works.
- Clicking Apply works in some cases.
- Some applications successfully reach "Applied" and this flow must NOT be broken.
- The major problem is that Naukri has multiple Apply outcomes.
- In some cases clicking Apply opens a sidebar/chatbot-style questionnaire where the bot cannot reliably detect the question/input field or enter the generated answer.
- There are also other possible outcomes such as already applied, login/session issues, CAPTCHA/manual intervention, external application pages, errors, and unknown UI states.

Your task is to HARDEN the existing Naukri application flow.

CRITICAL:
- Do NOT rewrite the entire Naukri automation.
- Do NOT replace the existing search/rotation/applier architecture.
- Do NOT change the working successful "Apply → Applied" path unnecessarily.
- Reuse the existing NaukriPlatform, SearchRotationEngine, applier, QnA engine, browser/session management, logging, and existing selectors/utilities.
- First inspect the current implementation and identify exactly where the Apply flow assumes a single UI structure.
- Make the smallest reliable changes necessary.
- Do not use arbitrary fixed sleeps as the primary synchronization mechanism.
- Do not create fake answers or fake success states.
- Never report an application as successful unless the UI actually confirms it.

==================================================
1. REDESIGN APPLY AS A STATE MACHINE
==================================================

The current logic must NOT assume:

Click Apply
    ↓
Questionnaire
    ↓
Submit

Instead implement/strengthen a state machine:

JOB_OPENED
    ↓
APPLY_CLICKED
    ↓
WAIT_FOR_APPLY_OUTCOME
    ├── ALREADY_APPLIED
    ├── APPLICATION_CONFIRMED
    ├── QUESTIONNAIRE_OPEN
    ├── CHATBOT_OPEN
    ├── EXTERNAL_APPLICATION
    ├── LOGIN_REQUIRED
    ├── CAPTCHA_OR_MANUAL_REQUIRED
    ├── ERROR
    └── UNKNOWN

Every branch must have explicit detection and handling.

==================================================
2. PRESERVE THE CURRENT SUCCESSFUL FLOW
==================================================

There is already a working case:

Click Apply
    ↓
Naukri displays "Applied" / equivalent confirmation
    ↓
Success

DO NOT modify this path unless required.

After clicking Apply, immediately check for application confirmation.

Possible confirmation indicators should be detected semantically rather than relying on only one CSS selector.

Examples of confirmation concepts:

- Applied
- Application submitted
- Already applied
- application success state
- button changing from Apply to Applied
- success confirmation/modal/toast

Use the existing DOM/selector utilities where available.

IMPORTANT:
"Applied" must be treated as a confirmed terminal state.

Log:

APPLICATION_CONFIRMED

with:
- job title
- company
- URL
- platform
- timestamp

Then return success to the existing application pipeline.

==================================================
3. AFTER APPLY CLICK, WAIT FOR THE ACTUAL UI OUTCOME
==================================================

Do NOT immediately search for a questionnaire input after clicking Apply.

Instead:

1. Click Apply.
2. Wait for one of the known outcome states.
3. Inspect the DOM.
4. Determine which flow appeared.
5. Route to the corresponding handler.

Use explicit waits / polling for DOM state changes.

Avoid:

time.sleep(5)

as the only synchronization mechanism.

Use a bounded wait such as:

WAIT_FOR_APPLY_OUTCOME

with a reasonable timeout.

During the wait check for:

- success confirmation
- already applied
- questionnaire
- chatbot/sidebar
- external URL/navigation
- login modal
- CAPTCHA/manual intervention
- error message

If none is detected after timeout:

UNKNOWN_APPLY_STATE

Do NOT blindly continue.

==================================================
4. QUESTIONNAIRE / CHATBOT FLOW
==================================================

This is the major failing case.

When Apply opens a sidebar/chatbot-style questionnaire, the bot must treat it as a separate application flow.

Do NOT assume the question input is:

<input type="text">

There may be:

- input
- textarea
- contenteditable div
- combobox
- custom React input
- dynamically generated input
- radio buttons
- checkboxes
- select/dropdown
- autocomplete
- custom chat input
- elements rendered after animation
- elements inside a nested container
- elements inside iframe/shadow DOM if actually present

The implementation must inspect the actual DOM structure before selecting the element.

==================================================
5. BUILD A ROBUST INPUT FINDER
==================================================

Create/use a semantic input-finding utility for the Naukri questionnaire.

The finder should inspect:

1. visible input elements
2. visible textarea elements
3. contenteditable elements
4. visible comboboxes
5. radio groups
6. checkbox groups
7. select elements
8. elements associated with labels
9. elements near the current question container

Do NOT simply select:

//input[1]

or:

input[type='text']

because the sidebar may contain multiple unrelated inputs.

The input finder must determine the input associated with the CURRENT QUESTION.

==================================================
6. QUESTION → INPUT ASSOCIATION
==================================================

For each questionnaire step:

1. Detect the currently visible question.
2. Extract the question text.
3. Locate the question container.
4. Search for the input/control inside or associated with that container.
5. Only then generate/select the answer.

Conceptually:

QUESTION CONTAINER
    ↓
Question text
    ↓
Answer type
    ↓
Associated control
    ↓
Answer
    ↓
Input
    ↓
Verification
    ↓
Next

Do not search the entire page for a generic input when a question-specific container exists.

==================================================
7. HANDLE DYNAMIC CHATBOT DOM
==================================================

The Naukri sidebar may dynamically replace the question and input.

Therefore:

DO NOT cache the WebElement for the entire questionnaire and reuse it indefinitely.

For every question:

- reacquire the current question element
- reacquire the current input element
- verify it is displayed
- verify it is enabled
- scroll it into view if necessary
- interact with it
- verify the entered value
- then continue

This avoids stale-element problems.

==================================================
8. RELIABLE TEXT INPUT
==================================================

When the answer is text:

Do not blindly call:

element.send_keys(answer)

and assume success.

Use a robust sequence:

1. Wait until visible.
2. Scroll into view.
3. Click/focus.
4. Clear existing value safely.
5. Enter answer.
6. Verify the DOM value/content actually changed.
7. If value is missing or incorrect, retry using the appropriate input strategy.
8. Only continue when verification succeeds.

Support both:

- normal input/textarea
- contenteditable controls

For React-controlled inputs, ensure the interaction produces the appropriate input/change events naturally through Selenium interaction.

Do NOT bypass normal application behavior with arbitrary JavaScript unless necessary and verified.

If JavaScript is required for a specific control, keep it isolated to that control and verify the resulting DOM state.

==================================================
9. INPUT VERIFICATION IS MANDATORY
==================================================

This is critical.

After entering an answer, verify:

For input/textarea:

element.get_attribute("value")

For contenteditable:

element.get_attribute("textContent")

or appropriate DOM property.

Expected:

entered answer is actually present.

If not:

INPUT_ENTRY_FAILED

Do NOT click Next/Submit.

Retry a bounded number of times.

Example:

ATTEMPT 1
    ↓
enter
    ↓
verify

if failed:

ATTEMPT 2
    ↓
refind element
    ↓
focus
    ↓
enter
    ↓
verify

if still failed:

MANUAL_REQUIRED / QUESTION_FAILED

Do not loop forever.

==================================================
10. SUPPORT NON-TEXT QUESTIONS
==================================================

The chatbot/questionnaire must not assume every question requires typing.

Support existing QnA engine answer types where possible:

TEXT
NUMBER
YES_NO
RADIO
CHECKBOX
DROPDOWN
AUTOCOMPLETE
DATE
UNKNOWN

For example:

"Are you willing to relocate?"

→ radio/button selection

"Years of experience?"

→ text/number

"Notice period?"

→ dropdown or text

"Preferred location?"

→ autocomplete

The QnA engine should determine the answer.

The browser layer should determine HOW to interact with the control.

Keep those responsibilities separate.

==================================================
11. REUSE EXISTING QNA ENGINE
==================================================

Do NOT create a second AI answering system.

Use the existing:

modules/qna_engine.py

or the project's existing QnA abstraction.

Flow:

Current question
    ↓
QnA engine
    ↓
answer + answer type
    ↓
Naukri interaction handler
    ↓
UI control
    ↓
verification

If the QnA engine cannot confidently answer:

QUESTION_UNRESOLVED

Do not invent an answer.

Follow the existing pause/manual policy.

==================================================
12. HANDLE NEXT / CONTINUE BUTTONS ROBUSTLY
==================================================

After successfully entering/selecting an answer:

Find the appropriate action button semantically.

Possible concepts:

Next
Continue
Submit
Apply
Finish

Do not assume a single fixed button selector.

Before clicking:

- ensure the button is visible
- ensure it is enabled
- ensure the current answer was successfully entered

After clicking:

wait for the next question or final confirmation.

Do NOT immediately search for the next input.

==================================================
13. DETECT QUESTION TRANSITIONS
==================================================

After clicking Next/Continue:

Wait until the previous question is replaced or the next question becomes visible.

Do not use:

sleep(2)

as the only mechanism.

Use DOM state changes.

The flow should be:

Question 1
    ↓
Answer verified
    ↓
Next
    ↓
WAIT FOR QUESTION CHANGE
    ↓
Question 2
    ↓
...

This prevents the bot from trying to type into stale/hidden controls.

==================================================
14. FINAL QUESTION / SUBMISSION
==================================================

After the last question:

Detect the final action explicitly.

Possible states:

SUBMIT
APPLY
FINISH
DONE
APPLICATION_CONFIRMED

Click only after all required answers have been successfully verified.

Then wait for final confirmation.

Success should only be recorded when:

APPLICATION_CONFIRMED

is detected.

If submission click happens but confirmation is not detected:

SUBMISSION_UNCONFIRMED

Do NOT immediately mark it as successful.

==================================================
15. OTHER APPLY CASES
==================================================

Implement explicit handlers for:

CASE A — Already Applied

Detect:
- Applied
- Already Applied
- application already exists

Result:

ALREADY_APPLIED

Do not submit again.

CASE B — Successful Direct Apply

Apply
    ↓
Applied

Result:

APPLICATION_CONFIRMED

CASE C — Questionnaire

Apply
    ↓
Sidebar/chatbot
    ↓
Questions
    ↓
Answers
    ↓
Submit
    ↓
Confirmation

Handle with questionnaire state machine.

CASE D — External Application

Apply
    ↓
external website/navigation

Detect URL/domain change.

Result:

EXTERNAL_APPLICATION

Do not claim Naukri submission success.

Log the external application URL.

CASE E — Login Required

If session/login page appears:

LOGIN_REQUIRED

Pause automation according to existing manual intervention architecture.

Do not attempt to bypass login.

CASE F — CAPTCHA / Human Verification

If CAPTCHA or human verification is detected:

CAPTCHA_OR_MANUAL_REQUIRED

Pause safely.

Do not attempt to bypass CAPTCHA.

Expose the existing manual intervention mechanism.

CASE G — Rate Limit / Block / Access Error

Detect relevant error state.

Result:

RATE_LIMITED / ACCESS_ERROR

Stop or pause according to existing safety policy.

CASE H — Apply Disabled

If Apply is disabled:

APPLY_UNAVAILABLE

Log reason if available.

CASE I — Unknown UI

If no known state is detected:

UNKNOWN_APPLY_STATE

Take a diagnostic screenshot and capture relevant DOM information.

Do NOT blindly continue.

==================================================
16. DIAGNOSTIC MODE FOR FAILURES
==================================================

This is extremely important because the Naukri UI may change.

Whenever a questionnaire/input interaction fails, capture diagnostics.

For example:

logs/naukri_debug/

job_<id>_<timestamp>/
    screenshot.png
    page_source.html
    current_url.txt
    question.txt
    detected_inputs.json
    detected_buttons.json
    error.txt

Only capture diagnostics when required/failure occurs, not continuously.

Never include passwords, session cookies, API keys, or other secrets in diagnostics.

==================================================
17. INPUT DEBUG INFORMATION
==================================================

When input detection fails, log structured information such as:

Question:
"What is your notice period?"

Detected controls:
- input[type=text] visible
- textarea hidden
- contenteditable false
- combobox visible

Selected control:
input[name="noticePeriod"]

Interaction:
send_keys

Verification:
FAILED

Reason:
value remained empty

Then retry using the fallback strategy.

This will make future Naukri DOM changes much easier to debug.

==================================================
18. SELECTOR ARCHITECTURE
==================================================

Do not scatter Naukri selectors throughout the code.

Keep selectors in the existing Naukri selector layer, for example:

platforms/naukri/selectors.py

Organize selectors semantically:

APPLY_BUTTON
APPLIED_INDICATOR
QUESTION_CONTAINER
QUESTION_TEXT
TEXT_INPUT
TEXTAREA
CONTENTEDITABLE
RADIO_OPTION
CHECKBOX
DROPDOWN
NEXT_BUTTON
SUBMIT_BUTTON
SUCCESS_INDICATOR
LOGIN_INDICATOR
CAPTCHA_INDICATOR
ERROR_INDICATOR

Where possible, maintain multiple fallback selectors.

But do not create dozens of speculative selectors without validating them against the actual DOM.

==================================================
19. WAIT STRATEGY
==================================================

Replace fragile fixed sleeps with:

- WebDriverWait
- expected conditions
- visibility checks
- enabled checks
- DOM/state polling
- bounded retries

Use small interaction delays only where required for normal browser behavior.

Never create infinite retries.

Every wait must have a timeout.

==================================================
20. IMPORTANT: DO NOT BREAK LINKEDIN
==================================================

This task is specifically for Naukri.

Do not modify:

LinkedIn automation
runAiBot.py
LinkedIn QnA behavior
LinkedIn selectors

unless a genuinely shared utility must be changed and existing LinkedIn tests continue to pass.

==================================================
21. APPLICATION RESULT MODEL
==================================================

Normalize Naukri outcomes internally so the rest of JobPilot does not need to understand DOM details.

Use semantic results such as:

APPLICATION_CONFIRMED
ALREADY_APPLIED
QUESTIONNAIRE_COMPLETED
EXTERNAL_APPLICATION
LOGIN_REQUIRED
CAPTCHA_OR_MANUAL_REQUIRED
RATE_LIMITED
APPLY_UNAVAILABLE
APPLICATION_FAILED
UNKNOWN_APPLY_STATE

The application service/database should only receive a successful application when the automation has sufficient evidence.

==================================================
22. IDEMPOTENCY / CRASH SAFETY
==================================================

Important:

If the browser crashes immediately after clicking Submit, do not blindly retry and potentially submit twice.

Before retrying:

check whether the job now shows:

Applied
Already Applied
Application submitted

If yes:

APPLICATION_CONFIRMED / ALREADY_APPLIED

If not:

follow the existing retry/manual policy.

Never assume:

"Submit clicked = success."

==================================================
23. TESTING
==================================================

Add/extend tests for each Apply branch.

Required scenarios:

1. test_direct_apply_success
2. test_already_applied
3. test_questionnaire_text_input
4. test_questionnaire_textarea
5. test_questionnaire_contenteditable
6. test_questionnaire_radio
7. test_questionnaire_dropdown
8. test_input_value_verification
9. test_input_retry_after_failed_entry
10. test_next_question_transition
11. test_questionnaire_final_submission
12. test_external_application
13. test_login_required
14. test_captcha_manual_required
15. test_rate_limited
16. test_apply_button_disabled
17. test_unknown_apply_state
18. test_submission_unconfirmed
19. test_no_duplicate_submission
20. test_diagnostic_capture_on_failure

Use mocked/fake DOM fixtures where practical.

Do not depend exclusively on the live Naukri website for automated tests.

==================================================
24. LIVE DEBUGGING REQUIREMENT
==================================================

Before changing selectors blindly:

Run the existing Naukri bot against one controlled test job.

When the chatbot/sidebar appears:

capture:

1. screenshot
2. page source
3. current URL
4. visible question text
5. all visible input/textarea/contenteditable elements
6. visible buttons
7. relevant element attributes

Then determine exactly why the current input interaction fails.

Do NOT guess the selector.

The implementation should be based on the actual DOM structure encountered.

==================================================
25. FINAL ACCEPTANCE CRITERIA
==================================================

The Naukri automation should correctly distinguish:

Apply
  ↓
┌────────────────────────────────────────────┐
│                                            │
│ Applied                                    │
│ → SUCCESS                                  │
│                                            │
│ Already Applied                            │
│ → ALREADY_APPLIED                          │
│                                            │
│ Questionnaire / Chatbot                    │
│ → QUESTIONNAIRE_HANDLER                    │
│                                            │
│ External Website                           │
│ → EXTERNAL_APPLICATION                     │
│                                            │
│ Login Required                             │
│ → LOGIN_REQUIRED                            │
│                                            │
│ CAPTCHA / Human Verification               │
│ → MANUAL_REQUIRED                           │
│                                            │
│ Rate Limit / Access Error                  │
│ → PAUSE/FAIL according to policy           │
│                                            │
│ Unknown                                    │
│ → DIAGNOSTIC + UNKNOWN_APPLY_STATE         │
│                                            │
└────────────────────────────────────────────┘

For questionnaire:

Question
  ↓
Detect question
  ↓
Determine answer type
  ↓
QnA engine
  ↓
Find associated control
  ↓
Enter/select answer
  ↓
VERIFY ANSWER
  ↓
Next
  ↓
WAIT FOR NEXT QUESTION
  ↓
Repeat
  ↓
Submit
  ↓
WAIT FOR CONFIRMATION
  ↓
APPLICATION_CONFIRMED

The primary objective is NOT to make the bot blindly click through every Naukri page.

The objective is to make the automation:
- deterministic
- observable
- recoverable
- resistant to DOM changes
- safe against duplicate applications
- explicit about unknown states
- reliable when interacting with dynamic questionnaire inputs.

At the end, run the complete existing test suite and verify that the previously working direct "Apply → Applied" flow remains unchanged and passing.