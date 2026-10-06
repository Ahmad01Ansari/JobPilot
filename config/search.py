



###################################################### LINKEDIN SEARCH PREFERENCES ######################################################


def _read_platform_from_db(platform_name="linkedin"):
    """Read platform config directly from SQLite DB (lightweight, no SQLAlchemy).

    This makes the DB the single source of truth for search terms and filters,
    keeping the bot subprocess aligned with the desktop app UI.
    """
    import json
    import os
    import sqlite3
    from pathlib import Path

    db_path = os.environ.get("JOBPILOT_DB_PATH")
    if db_path:
        db_path = Path(db_path)
    else:
        db_path = Path.home() / ".jobpilot" / "jobpilot.db"

    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        cur = conn.cursor()
        cur.execute("""
            SELECT pa.extra_settings, pa.default_location, pa.experience_years,
                   pa.max_applications, pa.apply_mode, pa.pause_before_submit,
                   pa.stealth_mode, pa.safe_mode, pa.daily_application_goal
            FROM platform_accounts pa
            JOIN platforms p ON pa.platform_id = p.id
            WHERE p.name = ?
            LIMIT 1
        """, (platform_name,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        extra = json.loads(row[0]) if row[0] else {}
        result = dict(extra)
        result["search_location"] = row[1]
        result["current_experience"] = row[2]
        result["switch_number"] = row[3]
        result["easy_apply_only"] = row[4] == "EASY_APPLY_ONLY"
        result["apply_mode"] = row[4] or "EASY_APPLY_ONLY"
        result["pause_before_submit"] = bool(row[5])
        result["stealth_mode"] = bool(row[6])
        result["safe_mode"] = bool(row[7])
        result["daily_application_goal"] = row[8] if len(row) > 8 and row[8] is not None else 50
        return result
    except Exception:
        return None


# Primary source: SQLite DB (shared with desktop UI)
_plat_db = _read_platform_from_db("linkedin")

# Fallback source: profile.json (used when DB doesn't exist yet)
try:
    from modules.config_loader import get_platform, load_profile
    load_profile(force_reload=True)
    _plat_file = get_platform("linkedin")
except Exception:
    _plat_file = {}

# Merge: DB values override profile.json values
_plat = {**_plat_file}
if _plat_db:
    _plat.update(_plat_db)

# These Sentences are Searched in LinkedIn
# Enter your search terms inside '[ ]' with quotes ' "searching title" ' for each search followed by comma ', ' Eg: ["Software Engineer", "Software Developer", "Selenium Developer"]
search_terms = _plat.get("search_terms", ["RPA Developer", "Automation Anywhere Developer", "Python Automation Engineer", "AI Automation Engineer", "Automation Engineer"])

# Search location, this will be filled in "City, state, or zip code" search box. If left empty as "", tool will not fill it.
search_location = _plat.get("search_location", "Delhi, India")              

# Search distance radius (e.g. 0 for exact city, 10 for ~16km, 25 for ~40km, 50 for ~80km, 100 for ~160km).
# None means LinkedIn default (which is 25 miles / 40 km for metropolitan cities).
distance = _plat.get("distance", None)

# After how many number of applications in current search should the bot switch to next search? 
switch_number = _plat.get("switch_number", 75)                 # Only numbers greater than 0... Don't put in quotes

# Daily application goal (maximum applications today before pausing with a safety dialog to prevent account restrictions)
daily_application_goal = _plat.get("daily_application_goal", 50)

# Do you want to randomize the search order for search_terms?
randomize_search_order = _plat.get("randomize_search_order", False)     # True of False, Note: True or False are case-sensitive


# >>>>>>>>>>> Job Search Filters <<<<<<<<<<<
''' 
You could set your preferences or leave them as empty to not select options except for 'True or False' options. Below are some valid examples for leaving them empty:
This is below format: QUESTION = VALID_ANSWER

## Examples of how to leave them empty. Note that True or False options cannot be left empty! 
* question_1 = ""                    # answer1, answer2, answer3, etc.
* question_2 = []                    # (multiple select)
* question_3 = []                    # (dynamic multiple select)

## Some valid examples of how to answer questions:
* question_1 = "answer1"                  # "answer1", "answer2", "answer3" or ("" to not select). Answers are case sensitive.
* question_2 = ["answer1", "answer2"]     # (multiple select) "answer1", "answer2", "answer3" or ([] to not select). Note that answers must be in [] and are case sensitive.
* question_3 = ["answer1", "Random AnswER"]     # (dynamic multiple select) "answer1", "answer2", "answer3" or ([] to not select). Note that answers must be in [] and need not match the available options.

'''

sort_by = _plat.get("sort_by", "")                       # "Most recent", "Most relevant" or ("" to not select) 
date_posted = _plat.get("date_posted", "Past week")         # "Any time", "Past month", "Past week", "Past 24 hours" or ("" to not select)
salary = ""                        # "$40,000+", "$60,000+", "$80,000+", "$100,000+", "$120,000+", "$140,000+", "$160,000+", "$180,000+", "$200,000+"

easy_apply_only = _plat.get("easy_apply_only", True)             # True or False, Note: True or False are case-sensitive

experience_level = []              # (multiple select) "Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"
job_type = []                      # (multiple select) "Full-time", "Part-time", "Contract", "Temporary", "Volunteer", "Internship", "Other"
on_site = []                       # (multiple select) "On-site", "Remote", "Hybrid"

companies = []                     # (dynamic multiple select) make sure the name you type in list exactly matches with the company name you're looking for, including capitals. 
                                   # Eg: "7-eleven", "Google","X, the moonshot factory","YouTube","CapitalG","Adometry (acquired by Google)","Meta","Apple","Byte Dance","Netflix", "Snowflake","Mineral.ai","Microsoft","JP Morgan","Barclays","Visa","American Express", "Snap Inc", "JPMorgan Chase & Co.", "Tata Consultancy Services", "Recruiting from Scratch", "Epic", and so on...
location = []                      # (dynamic multiple select)
industry = []                      # (dynamic multiple select)
job_function = []                  # (dynamic multiple select)
job_titles = []                    # (dynamic multiple select)
benefits = []                      # (dynamic multiple select)
commitments = []                   # (dynamic multiple select)

under_10_applicants = False        # True or False, Note: True or False are case-sensitive
in_your_network = False            # True or False, Note: True or False are case-sensitive
fair_chance_employer = False       # True or False, Note: True or False are case-sensitive


## >>>>>>>>>>> RELATED SETTING <<<<<<<<<<<

# Pause after applying filters to let you modify the search results and filters?
pause_after_filters = _plat.get("pause_after_filters", False)         # True or False, Note: True or False are case-sensitive

##




## >>>>>>>>>>> SKIP IRRELEVANT JOBS <<<<<<<<<<<
 
# Avoid applying to these companies, and companies with these bad words in their 'About Company' section...
about_company_bad_words = _plat.get("about_company_bad_words", ["Crossover"])       # (dynamic multiple search) or leave empty as []. Ex: ["Staffing", "Recruiting", "Name of Company you don't want to apply to"]

# Skip checking for `about_company_bad_words` for these companies if they have these good words in their 'About Company' section... [Exceptions, For example, I want to apply to "Robert Half" although it's a staffing company]
about_company_good_words = []      # (dynamic multiple search) or leave empty as []. Ex: ["Robert Half", "Dice"]

# Avoid applying to these companies if they have these bad words in their 'Job Description' section...  (In development)
bad_words = _plat.get("bad_words", ["US Citizen","USA Citizen","No C2C", "No Corp2Corp", "Embedded Programming", "PHP", "Ruby", "CNC"])                     # (dynamic multiple search) or leave empty as []. Case Insensitive. Ex: ["word_1", "phrase 1", "word word", "polygraph", "US Citizenship", "Security Clearance"]

# Do you have an active Security Clearance? (True for Yes and False for No)
security_clearance = False         # True or False, Note: True or False are case-sensitive

# Do you have a Masters degree? (True for Yes and False for No). If True, the tool will apply to jobs containing the word 'master' in their job description and if it's experience required <= current_experience + 2 and current_experience is not set as -1. 
did_masters = False                 # True or False, Note: True or False are case-sensitive

# Avoid applying to jobs if their required experience is above your current_experience. (Set value as -1 if you want to apply to all ignoring their required experience...)
current_experience = _plat.get("current_experience", 5)             # Integers > -2 (Ex: -1, 0, 1, 2, 3, 4...)

# Maximum pages to scrape per search keyword before automatically switching to the next keyword
max_pages_per_search = _plat.get("max_pages_per_search", 5)

# Switch to next search keyword early if this many consecutive jobs are skipped for irrelevance
consecutive_skips_limit = _plat.get("consecutive_skips_limit", 20)

# Negative keywords in Job Title to skip immediately in 0.01s without clicking or calling AI
negative_title_words = _plat.get("negative_title_words", [
    "electrical", "mechanical", "civil", "hardware", "chemical", "structural",
    "technician", "machinist", "maintenance", "site engineer", "eplan", "plc programmer"
])
##






############################################################################################################

