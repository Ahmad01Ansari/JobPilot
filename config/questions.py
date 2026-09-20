



###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Load from centralized profile.json if available
try:
    from modules.config_loader import get_professional, get_resume, get_qna, get_platform
    _prof = get_professional()
    _qna = get_qna()
    _std = _qna.get("standard_answers", {})
    _plat = get_platform("linkedin")
except Exception:
    _prof, _qna, _std, _plat = {}, {}, {}, {}

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = get_resume() if "get_resume" in locals() else "PersonalData/Mohd_Ahmad_Raza_Ansari_Resume_11_09_2026.pdf"

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience? 
years_of_experience = str(_prof.get("years_of_experience", "2"))

# Do you need visa sponsorship now or in future?
require_visa = _std.get("require_visa", "No")

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = _prof.get("portfolio_url", "https://github.com/Ahmad10Raza")


# Please provide the link to your LinkedIn profile.
linkedIn = _prof.get("linkedin_url", "https://www.linkedin.com/in/ahmad10raza/")

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = _std.get("us_citizenship", "Other")



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = int(_prof.get("desired_salary", 1200000))
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = int(_prof.get("current_ctc", 700000))            # 800000, 900000, 1000000 or 1200000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg: 
# currency = "INR"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = int(_prof.get("notice_period_days", 30))                   # Any number >= 0 without quotes. Eg: 0, 7, 15, 30, 45, etc.
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months), 
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = _prof.get("headline", "RPA Developer | AI Automation Engineer | Automation Anywhere 360 | Python | SAP Automation | IDP | Agentic AI")

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = _prof.get("summary", """
RPA Developer with approximately 2 years of hands-on experience building enterprise automation solutions using Automation Anywhere and Python. Experienced in SAP GUI automation, REST API integration, SQL/database workflows, OCR, and Intelligent Document Processing (IDP) across automotive and finance domains. Delivered automation across 42+ plants, processing 300+ document layouts, and reducing manual effort by up to 90%. Integrates OpenAI, Gemini, AWS Textract, and agentic AI workflows into RPA pipelines for intelligent document processing and multi-LLM validation.
""")

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = _prof.get("cover_letter", """Cover Letter""")

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc. 
user_information_all = _qna.get("ai_context", """User Information""")
##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = _prof.get("current_employer", "AventIQ AI")

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = str(_prof.get("confidence_level", "9"))
##



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = _plat.get("pause_before_submit", True)         # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = _plat.get("pause_at_failed_question", True)    # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False # True or False, Note: True or False are case-sensitive







############################################################################################################

