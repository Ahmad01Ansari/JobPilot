You are redesigning the existing JobPilot "Job Search Criteria" page into a
production-grade, modern ATS/job-search automation configuration workspace.

The current page already contains working configuration such as:

- Target platform
- Apply criteria to all platforms
- Target location
- Date posted
- Max experience
- Max pages / keyword
- Switch after N applications
- Consecutive skip limit
- Easy Apply only
- Continuous automation mode
- Automatic date-posted cycling
- Alternate search sort order
- Stop date cycle at 24 hours
- Negative title words
- Job description blacklist words
- Load RPA / Auto exclusions
- Load Standard Blacklist
- Save / Reset
- Sync from Resume

The goal is NOT to rewrite this functionality.

The goal is to transform it into a modern, intuitive, production-ready
ATS-style "Search Strategy Builder" while preserving all existing
configuration behavior and compatibility with LinkedIn/Naukri automation.

============================================================
CRITICAL RULES
============================================================

1. DO NOT rewrite LinkedIn automation.

2. DO NOT rewrite Naukri automation.

3. DO NOT change existing automation behavior merely for UI purposes.

4. DO NOT rename existing configuration keys without an explicit migration.

5. DO NOT silently change the meaning of existing settings.

6. Reuse the existing configuration/profile/search service layer.

7. Do not create fake settings that are not connected to real backend behavior.

8. Every visible setting must either:
   - map to an existing configuration value, OR
   - be explicitly implemented end-to-end before being shown as enabled.

9. If a proposed feature cannot currently be supported by the backend,
   show it as unavailable/disabled or omit it rather than creating a
   fake control.

10. Preserve backward compatibility with:
    - config/profile.json
    - existing LinkedIn search configuration
    - existing Naukri search configuration
    - search rotation logic
    - existing automation services

11. Existing tests must continue to pass.

12. Do not modify tests simply to make the redesign pass.

============================================================
PRIMARY UX OBJECTIVE
============================================================

Transform:

"Job Search Criteria"

from a long configuration form into:

"Job Search Strategy"

The user should be able to understand the entire search strategy at a glance.

The page should answer:

1. What roles am I searching for?
2. Where am I searching?
3. Which platforms?
4. How much experience?
5. How fresh should jobs be?
6. Which job types/methods are allowed?
7. What should be skipped immediately?
8. What should be rejected after reading the description?
9. How should automation rotate searches?
10. How many jobs should it process?
11. Is continuous mode enabled?
12. Is the configuration valid?
13. Are there unsaved changes?

============================================================
NEW INFORMATION ARCHITECTURE
============================================================

Do NOT keep the current giant vertical form.

Use a structured configuration workspace:

------------------------------------------------------------

PAGE HEADER

Job Search Strategy

"Define what JobPilot should search, prioritize, and skip."

[ Sync from Resume ]
[ Reset ]
[ Save Strategy ]

------------------------------------------------------------

STRATEGY SUMMARY

A compact summary card:

Searching for:
RPA Developer · Automation Anywhere Developer · Python Automation

Platforms:
LinkedIn · Naukri

Location:
Bangalore

Experience:
0–5 years

Freshness:
Past week

Application:
Easy Apply

Automation:
Continuous

[ Edit Strategy ]

------------------------------------------------------------

SECTION 1
TARGET ROLES

------------------------------------------------------------

SECTION 2
WHERE & EXPERIENCE

------------------------------------------------------------

SECTION 3
SEARCH & APPLICATION PREFERENCES

------------------------------------------------------------

SECTION 4
AUTOMATION BEHAVIOR

------------------------------------------------------------

SECTION 5
INSTANT SKIP RULES

------------------------------------------------------------

SECTION 6
JOB DESCRIPTION FILTERS

------------------------------------------------------------

SECTION 7
ADVANCED / PLATFORM SETTINGS

------------------------------------------------------------

STICKY SAVE BAR

[ Unsaved changes ]
[ Reset changes ]
[ Save Strategy ]

============================================================
1. TARGET ROLES — FIRST-CLASS FEATURE
============================================================

This is one of the most important missing pieces.

Create a dedicated:

"Target Roles"

section.

Subtitle:

"Tell JobPilot which job titles and search terms to rotate through."

Example:

TARGET KEYWORDS

[ RPA Developer                    × ]
[ Automation Anywhere Developer   × ]
[ Python Automation Engineer      × ]
[ AI Automation Engineer          × ]

Input:

[ + Add keyword ]

Support:

- Enter to add
- comma-separated paste
- duplicate prevention
- remove individual keyword
- reorder keywords
- drag-and-drop ordering if practical
- keyword count

Example:

4 search keywords

------------------------------------------------------------

KEYWORD ORDER

Allow:

Most relevant
Most recent

or existing configured sort behavior.

If the existing automation rotates keywords in a specific order, preserve
that behavior.

------------------------------------------------------------

SYNC FROM RESUME

Keep:

[ Sync from Resume ]

But make it understandable.

When clicked:

Review suggested keywords

☑ RPA Developer
☑ Automation Engineer
☑ Python Automation
☐ Data Scientist

[ Add Selected ]

Do not automatically overwrite existing keywords.

Instead provide:

Merge
Replace
Cancel

unless the current backend already defines different behavior.

============================================================
2. PLATFORM SELECTION
============================================================

Replace the current:

Target Platform:
LinkedIn

with a more modern platform selector.

Example:

SEARCH PLATFORMS

[ ✓ LinkedIn ]
[ ✓ Naukri ]
[   Indeed ]
[   Glassdoor ]

Only enable platforms actually supported by the current automation.

Show:

LinkedIn
Ready

Naukri
Ready

Indeed
Not configured

Do not allow a platform to appear as executable if there is no working
automation engine.

------------------------------------------------------------

ALL PLATFORMS

The existing:

"Apply this search criteria to ALL platforms"

should become:

[ ✓ Use this strategy across selected platforms ]

Explain:

"Use the same search strategy for all enabled platforms."

If platform-specific overrides are supported, allow:

[ Configure platform overrides ]

Do not duplicate the entire form unnecessarily.

============================================================
3. LOCATION
============================================================

Improve:

Target Location: Bangalore

into:

TARGET LOCATIONS

[ Bangalore × ]
[ Hyderabad × ]
[ Delhi NCR × ]

[ + Add location ]

Support multiple locations if the underlying search engine already supports
them.

If only one location is currently supported, retain single-location behavior
and make the UI architecture ready for future multi-location support.

Do not fake multi-location execution.

------------------------------------------------------------

REMOTE / WORK MODE

If supported by the current backend, add:

Work Mode

[ Any ]
[ Remote ]
[ Hybrid ]
[ On-site ]

If not supported, do not show it as an active setting.

============================================================
4. EXPERIENCE
============================================================

Replace the current scattered numeric controls with:

EXPERIENCE

Minimum:
[ 0 ] years

Maximum:
[ 5 ] years

Show a compact range representation:

0 ─────────────── 5 years

Validation:

min <= max

No negative values.

Do not silently convert invalid values.

============================================================
5. JOB FRESHNESS
============================================================

Create:

JOB FRESHNESS

[ Past 24 hours ]
[ Past 3 days ]
[ Past week ]
[ Past month ]

Use the existing supported date-posted values.

If the current system uses a specific internal representation, keep that
mapping unchanged.

------------------------------------------------------------

AUTOMATIC FRESHNESS ROTATION

If existing automation supports:

24hr → week → month

show:

[ ✓ Automatically expand search freshness ]

Visual explanation:

24 hours
↓
Past week
↓
Past month

Only show this when the corresponding backend behavior exists.

============================================================
6. APPLICATION PREFERENCES
============================================================

Create a clear section:

APPLICATION PREFERENCES

Application method:

[ ✓ Easy Apply ]

If Company Portal / External application is supported in the search strategy,
allow:

[ ✓ Easy Apply ]
[ ✓ Company Portal ]

Do not add unsupported application types.

------------------------------------------------------------

SEARCH RESULT LIMITS

Max pages / keyword:
[ 5 ]

Show explanation:

"Maximum search result pages processed for each keyword."

------------------------------------------------------------

APPLICATION ROTATION

Switch after:
[ 78 ] applications

Consecutive skips:
[ 20 ]

Explain each setting with small helper text.

Avoid technical labels without explanations.

============================================================
7. AUTOMATION BEHAVIOR
============================================================

Move these existing settings into a dedicated section.

AUTOMATION BEHAVIOR

[ ✓ Continuous search mode ]

Description:
"Continue rotating through configured searches until stopped."

[ ✓ Automatically cycle job freshness ]

[ ✓ Alternate search sort order ]

[ ✓ Stop freshness cycle at 24 hours ]

Use dependency behavior.

For example:

If continuous mode is OFF,
freshness cycling controls may become visually disabled if they have no
meaning outside continuous execution.

Do not delete their values.

============================================================
8. SEARCH SORTING
============================================================

If supported by the current backend:

SEARCH PRIORITY

[ Most Recent ]
[ Most Relevant ]

Existing:

"Alternate search sort order"

should be represented as:

[ ✓ Alternate between search sorting modes ]

Example:

Most Recent
↓
Most Relevant
↓
Most Recent

Do not change the underlying rotation logic.

============================================================
9. INSTANT SKIP RULES
============================================================

This should become a dedicated "Skip Rules" workspace.

Title:

INSTANT SKIP RULES

Subtitle:

"Jobs matching these title keywords are skipped before opening the listing."

Example chips:

android ×
ios ×
full stack ×
frontend ×
react ×
angular ×
vue ×
java developer ×
dot net ×
c++ ×
php ×
flutter ×
salesforce ×
devops ×
cloud architect ×
mechanical ×
civil ×

Use a proper tag/chip input.

------------------------------------------------------------

INPUT

[ Type a keyword and press Enter ]

Buttons:

[ Add ]
[ Load RPA / Auto Exclusions ]

------------------------------------------------------------

BULK ACTIONS

If useful:

[ Import ]
[ Export ]
[ Clear All ]

Only implement Import/Export if there is an appropriate existing
configuration mechanism.

------------------------------------------------------------

IMPORTANT

Duplicate keywords should not be added.

Normalize whitespace.

Do not unexpectedly lowercase values if case sensitivity has meaning in the
existing matching engine.

============================================================
10. DESCRIPTION BLACKLIST
============================================================

Create another visually distinct section:

DESCRIPTION FILTERS

Subtitle:

"Skip jobs after reading the description when these terms are detected."

Example:

US Citizen Only ×
Active Security Clearance ×
Polygraph ×
CNC Operator ×
No C2C ×
Unpaid Internship ×

Use the same tag-input component as title exclusions.

This provides consistency.

------------------------------------------------------------

STANDARD BLACKLIST

[ Load Standard Blacklist ]

Explain:

"Adds the predefined description exclusion rules."

Do not overwrite custom rules without confirmation.

============================================================
11. NEW OPTIONAL FILTERS
============================================================

Before implementing any of these, inspect whether the existing backend
already supports them.

Potential filters:

- salary range
- job type
- remote/hybrid/on-site
- company exclusions
- company inclusion list
- seniority
- employment type
- visa sponsorship
- relocation
- industry
- posted date
- location radius

IMPORTANT:

Do not create UI controls that have no backend behavior.

If a feature is valuable but unsupported, place it in an:

"Planned Filters"

or leave it out.

Do not fake functionality.

============================================================
12. COMPANY EXCLUSION RULES
============================================================

If supported by the existing filtering architecture, add:

COMPANY RULES

Excluded companies:

[ Company A × ]
[ Company B × ]

[ Add company ]

This is useful for preventing repeated applications to companies that should
be skipped.

Only implement if the automation can actually consume this configuration.

============================================================
13. SEARCH PREVIEW
============================================================

Add an important feature:

[ Preview Search ]

Before running automation, show:

SEARCH PREVIEW

Platforms:
LinkedIn · Naukri

Keywords:
4

Locations:
Bangalore

Experience:
0–5 years

Freshness:
Past week

Method:
Easy Apply

Expected searches:

LinkedIn
RPA Developer
Bangalore
Easy Apply

LinkedIn
Automation Anywhere Developer
Bangalore
Easy Apply

Naukri
RPA Developer
Bangalore

...

This should be generated from the actual saved configuration.

Do not execute automation.

The purpose is to allow the user to verify the strategy before saving/running.

If preview generation cannot be performed without platform access, provide a
configuration-only preview rather than pretending to query job sites.

============================================================
14. VALIDATION PANEL
============================================================

Before Save:

display configuration health.

Example:

✓ 4 keywords configured
✓ Platform configured
✓ Location configured
✓ Experience range valid
✓ Easy Apply enabled
⚠ Naukri credentials not configured

If there are blocking issues:

✕ No target keywords configured

[ Fix ]

The user should understand why a strategy cannot run.

============================================================
15. UNSAVED CHANGES
============================================================

Implement proper dirty-state tracking.

When a field changes:

Show:

Unsaved changes

[ Discard ]
[ Save Strategy ]

If the user navigates away with unsaved changes:

Ask:

"You have unsaved search criteria.
Save changes before leaving?"

[ Save ]
[ Discard ]
[ Cancel ]

Do not lose user configuration silently.

============================================================
16. SAVE BEHAVIOR
============================================================

The current:

[ Save Criteria ]

should become:

[ Save Strategy ]

After successful save:

✓ Search strategy saved

Show a temporary toast/status message.

Do not use modal dialogs for simple success messages.

If saving fails:

✕ Unable to save search strategy

[ Retry ]

============================================================
17. RESET BEHAVIOR
============================================================

Current:

Reset

should become:

[ Reset ]

But distinguish:

Reset unsaved changes

from:

Restore defaults

Do NOT accidentally wipe the user's stored configuration.

If restoring defaults:

"Restore default search strategy?"

[ Restore Defaults ]
[ Cancel ]

============================================================
18. SEARCH PRESETS
============================================================

This would be a valuable ATS feature if the backend can support it cleanly.

Allow saved strategies such as:

RPA / Automation
AI Automation
Python Automation
Data Science

Example:

[ RPA Automation ▾ ]

[ Save as New Strategy ]

If the existing backend does not support multiple saved profiles, DO NOT
implement fake persistence.

Instead design the UI so presets can be added later.

============================================================
19. PLATFORM OVERRIDES
============================================================

Because LinkedIn and Naukri may have different search capabilities, do not
force all settings to be identical.

Example:

GLOBAL STRATEGY

Keywords:
RPA Developer
Automation Anywhere Developer

Location:
Bangalore

Then:

PLATFORM OVERRIDES

LinkedIn
Freshness: Past week
Easy Apply: Yes

Naukri
Freshness: Past 3 days
Quick Apply: Yes

Only expose actual platform-specific settings.

Use inheritance:

Global
↓
Platform override

Do not duplicate the entire configuration.

============================================================
20. RESPONSIVE LAYOUT
============================================================

The current page uses very wide rows.

Use a responsive two-column layout where appropriate:

Desktop:

LEFT 60%
Core search strategy

RIGHT 40%
Strategy summary / validation / automation behavior

Or:

Full width for major sections with compact two-column field groups.

Avoid extremely long single horizontal rows.

Example:

Target Location
[ Bangalore ]

Experience
[ 0 ] – [ 5 ]

Date Posted
[ Past week ]

Max Pages
[ 5 ]

This is easier to scan.

============================================================
21. SECTION COLLAPSING
============================================================

Long configuration sections should be collapsible.

Default expanded:

Target Roles
Location & Experience
Search Preferences

Optional/collapsed:

Advanced Automation
Skip Rules
Description Filters
Platform Overrides

Remember expanded/collapsed state if the existing settings system supports it.

Do not hide critical configuration behind too many accordions.

============================================================
22. STICKY SAVE BAR
============================================================

Because this page can become long, add a sticky bottom action bar:

────────────────────────────────────────────────────────

● Unsaved changes

[ Reset Changes ]                         [ Save Strategy ]

────────────────────────────────────────────────────────

When there are no changes:

Strategy saved ✓

The save action should remain accessible without scrolling back to the top.

============================================================
23. COLOR SYSTEM
============================================================

The current orange is useful but overused.

Use semantic design tokens.

Primary brand:
Orange

Use orange for:

- primary CTA
- active controls
- important interactive elements

Do NOT use orange for every section heading.

Section headings should use normal primary text.

Use:

Success → green
Warning → amber
Danger → red
Info → blue
Neutral → slate

Tags/chips should use subtle surfaces.

Avoid:

- neon orange
- heavy gradients
- excessive glowing
- black boxes inside black boxes

============================================================
24. DARK + LIGHT THEME
============================================================

The page must fully support:

DARK
LIGHT

Dark:

near-black background
dark elevated surfaces
subtle slate borders
white primary text
muted secondary text

Light:

soft gray background
white surfaces
light borders
dark text
muted slate text

Do not simply invert the dark theme.

Every widget must use central theme/design tokens.

============================================================
25. FORM COMPONENT DESIGN
============================================================

Create reusable modern components:

SearchKeywordInput
TagInput
MultiSelect
NumberInput
RangeInput
PlatformSelector
SectionCard
ToggleRow
FilterChip
ValidationMessage
StrategySummary
StickySaveBar

Do not create dozens of tiny components unnecessarily.

Reuse the same tag-input component for:

Target keywords
Negative title words
Description blacklist
Company exclusions

============================================================
26. HELPER TEXT
============================================================

Every non-obvious automation setting should have concise helper text.

Bad:

Switch After N Applications

Better:

Switch search keyword after this many successful application attempts.

Bad:

Consecutive Skips Limit

Better:

Stop the current keyword after this many consecutive skipped jobs.

Do not make helper text overly verbose.

============================================================
27. FIELD VALIDATION
============================================================

Validate:

Keywords:
- not empty
- no duplicates

Location:
- required when platform search requires it

Experience:
- min >= 0
- max >= min

Max pages:
- positive integer

Switch after:
- positive integer

Consecutive skips:
- positive integer

Do not allow invalid values to be saved.

Use inline validation rather than modal error dialogs.

============================================================
28. CONFIGURATION COMPATIBILITY
============================================================

Before implementation, inspect the actual configuration schema.

Map each UI field to its existing key.

Create an explicit mapping document/code structure:

UI field
    ↓
configuration key
    ↓
existing automation consumer

Example:

Target keywords
→ profile.json keyword list
→ SearchRotationEngine

Location
→ profile.json location
→ platform search

Max pages
→ existing search page configuration
→ search engine

Negative title words
→ existing exclusion configuration
→ prefilter

Do not rename keys casually.

If the existing config has legacy names, preserve them internally.

============================================================
29. SAVE ATOMICALLY
============================================================

If profile.json is still used:

Do not write directly in a way that can corrupt the file.

Use the existing configuration service if available.

Otherwise use safe atomic write:

temporary file
↓
validate
↓
replace original

Do not modify config if validation fails.

============================================================
30. AUTOMATION SAFETY
============================================================

If automation is currently running and the user changes search criteria:

Do not silently mutate the active automation configuration.

Choose the existing safe behavior or implement:

"Changes will apply to the next automation run."

Example:

Automation running

Current strategy:
RPA Developer · Bangalore

User edits keywords.

Show:

"Changes saved for the next run.
Current automation will continue with its existing configuration."

Do not break an active Selenium process.

============================================================
31. KEYWORD ROTATION PREVIEW
============================================================

Because JobPilot uses keyword rotation, provide a small preview.

Example:

SEARCH ROTATION

1. RPA Developer
2. Automation Anywhere Developer
3. Python Automation Engineer
4. AI Automation Engineer

Estimated search combinations:

4 keywords × 2 platforms = 8 search configurations

Only calculate combinations from actual selected values.

Do not claim "estimated jobs."

============================================================
32. SEARCH STRATEGY SUMMARY
============================================================

Make the right/top summary highly useful.

Example:

SEARCH STRATEGY

4 keywords
2 platforms
1 location
0–5 years
Past week
Easy Apply

Automation:
Continuous

Skip rules:
24 title exclusions
6 description exclusions

Status:

✓ Ready to run

This is much more useful than a generic configuration page.

============================================================
33. ADVANCED SETTINGS
============================================================

Do not overwhelm the main screen.

Move less frequently changed options into:

Advanced Automation

Examples:

- alternate sort order
- continuous cycle
- date cycling
- stop cycle
- consecutive skip behavior

The user should be able to configure common search criteria without seeing
automation internals immediately.

============================================================
34. ACCESSIBILITY
============================================================

Ensure:

- keyboard navigation
- visible focus state
- readable labels
- accessible checkboxes
- tooltips
- sufficient contrast
- no color-only meaning
- Enter adds tags
- Escape closes popups
- Ctrl/Cmd+S saves strategy if no existing shortcut conflicts

============================================================
35. TESTING
============================================================

Create/update tests for:

1. Search page renders
2. Existing config loads correctly
3. Keyword add
4. Keyword remove
5. Duplicate keyword prevention
6. Keyword ordering
7. Location configuration
8. Experience validation
9. Date-posted selection
10. Max pages validation
11. Switch-after validation
12. Consecutive skip validation
13. Easy Apply toggle
14. Continuous mode
15. Date cycling
16. Sort cycling
17. Negative title tags
18. Description blacklist tags
19. Load standard blacklist
20. Load RPA exclusions
21. Multiple filters
22. Dirty-state tracking
23. Save strategy
24. Reset unsaved changes
25. Restore defaults
26. Search preview
27. Strategy validation
28. Dark theme
29. Light theme
30. Platform selection
31. All-platform configuration
32. Configuration backward compatibility
33. Running automation does not mutate active configuration
34. Atomic profile save
35. Invalid configuration cannot be saved

Do not rely only on visual tests.

Verify actual configuration values remain unchanged after save/load.

============================================================
36. VISUAL QA
============================================================

Generate screenshots for:

1. Default page — dark
2. Default page — light
3. Keyword configuration
4. Multiple filters configured
5. Skip rules
6. Description blacklist
7. Advanced settings expanded
8. Validation warning
9. Unsaved changes state
10. Search preview
11. Empty/no-keyword state
12. Narrow desktop layout

Test at:

1920 × 1080
1600 × 900
1366 × 768

The page must remain usable without excessive scrolling.

============================================================
37. FINAL VISUAL DIRECTION
============================================================

The final page should NOT look like:

"large dark form with orange section titles."

It should look like:

"a polished ATS search strategy builder."

Visual hierarchy:

1. Target roles
2. Search scope
3. Search preferences
4. Filtering rules
5. Automation behavior
6. Validation
7. Save

The user should understand the configuration within 5 seconds.

Use:

- modern SaaS spacing
- compact controls
- clean typography
- subtle surfaces
- semantic chips
- strong primary CTA
- consistent icons
- responsive two-column layouts
- sticky save controls
- excellent empty/validation states

Avoid:

- giant empty containers
- unnecessary borders
- excessive rounded cards
- orange everywhere
- huge labels
- dense horizontal rows
- technical terminology without explanation
- fake settings
- fake search results

============================================================
FINAL ACCEPTANCE CRITERIA
============================================================

The redesign is complete only when:

✓ Existing configuration behavior is preserved
✓ Existing profile/config keys remain compatible
✓ LinkedIn automation remains unchanged
✓ Naukri automation remains unchanged
✓ Keywords are first-class and manageable
✓ Multiple search criteria are easy to understand
✓ Filters are logically grouped
✓ Negative title rules remain functional
✓ Description blacklist remains functional
✓ Search rotation remains functional
✓ Continuous mode remains functional
✓ Date cycling remains functional
✓ Easy Apply remains functional
✓ Sync from Resume remains functional
✓ Save works
✓ Reset works safely
✓ Unsaved changes are detected
✓ Invalid settings cannot be saved
✓ Search strategy preview reflects real configuration
✓ Configuration validation is visible
✓ Dark theme works
✓ Light theme works
✓ Responsive layout works
✓ Existing tests pass
✓ No fake backend functionality
✓ No automation engine rewrite

FINAL PRODUCT GOAL:

JobPilot should feel like a professional ATS where the user creates a
"Search Strategy" rather than filling out a traditional settings form.

The mental model should be:

TARGET ROLES
      ↓
SEARCH SCOPE
      ↓
SEARCH PREFERENCES
      ↓
FILTER / SKIP RULES
      ↓
AUTOMATION BEHAVIOR
      ↓
VALIDATE
      ↓
SAVE STRATEGY
      ↓
RUN AUTOMATION
