'''
Bot Settings & Execution Preferences
'''


###################################################### CONFIGURE YOUR BOT HERE ######################################################

# Load from centralized profile.json if available
try:
    from modules.config_loader import get_platform, load_profile
    load_profile(force_reload=True)
    _plat = get_platform("linkedin")
except Exception:
    _plat = {}

# >>>>>>>>>>> LinkedIn Settings <<<<<<<<<<<

# Keep the External Application tabs open?
close_tabs = True                   # True or False, Note: True or False are case-sensitive
'''
Note: RECOMMENDED TO LEAVE IT AS `True`, if you set it `False`, be sure to CLOSE ALL TABS BEFORE CLOSING THE BROWSER!!!
'''

# Follow easy applied companies
follow_companies = False            # True or False, Note: True or False are case-sensitive

## Upcoming features (In Development)
# # Send connection requests to HR's 
# connect_hr = True                  # True or False, Note: True or False are case-sensitive

# # What message do you want to send during connection request? (Max. 200 Characters)
# connect_request_message = ""       # Leave Empty to send connection request without personalized invitation (recommended to leave it empty, since you only get 10 per month without LinkedIn Premium*)

# Do you want the program to run continuously until you stop it? (Beta)
run_non_stop = bool(_plat.get("run_non_stop", False))                # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
alternate_sortby = bool(_plat.get("alternate_sortby", True))             # True or False, Note: True or False are case-sensitive
cycle_date_posted = bool(_plat.get("cycle_date_posted", True))            # True or False, Note: True or False are case-sensitive
stop_date_cycle_at_24hr = bool(_plat.get("stop_date_cycle_at_24hr", True))      # True or False, Note: True or False are case-sensitive
sleep_duration_minutes = int(_plat.get("sleep_duration_minutes", 10))     # Duration in minutes the bot sleeps between cycles (0 = disabled)
sleep_mode_enabled = bool(_plat.get("sleep_mode_enabled", True)) and sleep_duration_minutes > 0





# >>>>>>>>>>> RESUME GENERATOR (Experimental & In Development) <<<<<<<<<<<

# Give the path to the folder where all the generated resumes are to be stored
generated_resume_path = "all resumes/" # (In Development)





# >>>>>>>>>>> Global Settings <<<<<<<<<<<

# Load from centralized profile.json if available
try:
    from modules.config_loader import get_platform
    _plat = get_platform("linkedin")
except Exception:
    _plat = {}

# Directory and name of the files where history of applied jobs is saved (Sentence after the last "/" will be considered as the file name).
file_name = "all excels/all_applied_applications_history.csv"
try:
    from app.services.os.app_paths import AppPaths
    logs_folder_path = str(AppPaths.get_logs_dir()) + "/"
except Exception:
    logs_folder_path = "logs/"

# Set the maximum amount of time allowed to wait between each click in secs
click_gap = _plat.get("click_gap", 1)                       # Enter max allowed secs to wait approximately. (Only Non Negative Integers Eg: 0,1,2,3,....)

# If you want to see Chrome running then set run_in_background as False (May reduce performance). 
run_in_background = _plat.get("run_in_background", False)           # True or False, Note: True or False are case-sensitive ,   If True, this will make pause_at_failed_question, pause_before_submit and run_in_background as False

# If you want to disable extensions then set disable_extensions as True (Better for performance)
disable_extensions = False          # True or False, Note: True or False are case-sensitive

# Run in safe mode. Set this true if chrome is taking too long to open or if you have multiple profiles in browser. This will open chrome in guest profile!
safe_mode = _plat.get("safe_mode", True)                    # True or False, Note: True or False are case-sensitive

# Do you want scrolling to be smooth or instantaneous? (Can reduce performance if True)
smooth_scroll = False               # True or False, Note: True or False are case-sensitive

# If enabled (True), the program would keep your screen active and prevent PC from sleeping. Instead you could disable this feature (set it to false) and adjust your PC sleep settings to Never Sleep or a preferred time. 
keep_screen_awake = _plat.get("keep_screen_awake", True)            # True or False, Note: True or False are case-sensitive (Note: Will temporarily deactivate when any application dialog boxes are present (Eg: Pause before submit, Help needed for a question..))

# Run in undetected mode to bypass anti-bot protections (Preview Feature, UNSTABLE. Recommended to leave it as False)
stealth_mode = _plat.get("stealth_mode", True)                # True or False, Note: True or False are case-sensitive

# Do you want to get alerts on errors related to AI API connection?
showAiErrorAlerts = False            # True or False, Note: True or False are case-sensitive

# Use ChatGPT for resume building (Experimental Feature can break the application. Recommended to leave it as False) 
# use_resume_generator = False       # True or False, Note: True or False are case-sensitive ,   This feature may only work with 'stealth_mode = True'. As ChatGPT website is hosted by CloudFlare which is protected by Anti-bot protections!











############################################################################################################