'''
Unified QnA Engine with Answer Provenance & Pre-Submission Validation
Intelligent, multi-tier question answering for job applications across platforms.
Tracks answer provenance (profile, rule, calculation, llm, manual) and validates constraints before submission.
'''

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Dict, Literal

from modules.config_loader import get_personal, get_professional, get_qna, get_ai

AnswerSource = Literal["profile", "rule", "calculation", "llm", "manual"]


@dataclass
class Answer:
    """Represents a resolved question answer with full provenance and validation metadata."""
    value: Any
    source: AnswerSource
    confidence: float
    field_type: str = "text"                      # "text", "number", "boolean", "select", "radio"
    validated: bool = True
    validation_error: Optional[str] = None

    def __str__(self) -> str:
        return str(self.value)


def validate_answer(
    answer: Answer,
    question_label: str,
    available_options: Optional[List[str]] = None,
) -> Answer:
    """Enforces domain constraints on generated answers before submission.
    Guarantees the LLM or rules engine never blindly submits invalid values.
    """
    lbl = question_label.lower().strip()
    val_str = str(answer.value).strip()

    # 1. Notice Period Validation
    if any(w in lbl for w in ["notice", "joining"]):
        # Extract numbers (including negative sign if any)
        nums = re.findall(r'-?\d+', val_str)
        if nums:
            days = int(nums[0])
            if "month" in val_str.lower():
                days = days * 30
            elif "week" in val_str.lower():
                days = days * 7
            if not (0 <= days <= 180):
                answer.validated = False
                answer.validation_error = f"Notice period {days} days is outside reasonable bounds (0-180 days)"
                return answer
        elif not any(term in val_str.lower() for term in ["immediate", "serving", "buyout", "day", "month"]):
            answer.validated = False
            answer.validation_error = f"Unrecognized notice period response: '{val_str}'"
            return answer

    # 2. Compensation / CTC Validation
    if any(w in lbl for w in ["ctc", "salary", "pay", "compensation"]):
        num_match = re.search(r'-?\d+(?:\.\d+)?', val_str.replace(",", ""))
        if num_match:
            try:
                num_val = float(num_match.group(0))
                if any(t in lbl for t in ["lakh", "lac", "lpa"]):
                    if not (0.5 <= num_val <= 100.0):
                        answer.validated = False
                        answer.validation_error = f"Salary {num_val} Lacs is outside realistic bounds (0.5-100 Lacs)"
                        return answer
                elif "month" in lbl:
                    if not (5000 <= num_val <= 5000000):
                        answer.validated = False
                        answer.validation_error = f"Monthly salary {num_val} is outside realistic bounds"
                        return answer
                else:
                    # Annual INR
                    if num_val < 50000 or num_val > 100000000:
                        answer.validated = False
                        answer.validation_error = f"Suspicious annual compensation value: {num_val}"
                        return answer
            except ValueError:
                pass
        else:
            answer.validated = False
            answer.validation_error = f"Could not extract numeric compensation from '{val_str}'"
            return answer

    # 3. Years of Experience Validation (only for numeric questions, not boolean Yes/No or qualitative questions)
    is_boolean_choice = False
    if available_options:
        opts_set = {o.strip().lower() for o in available_options}
        if opts_set.issubset({"yes", "no", "agree", "disagree", "true", "false"}):
            is_boolean_choice = True

    is_qualitative_exp = (
        any(lbl.startswith(p) for p in ["do you have", "have you", "are you", "any experience", "describe", "explain", "please provide", "share"])
        or "do you have experience" in lbl
        or "have experience" in lbl
        or "experience in the area" in lbl
    )

    if not is_boolean_choice and not is_qualitative_exp and any(w in lbl for w in ["years of experience", "how many years", "total years", "total experience"]):
        num_match = re.search(r'-?\d+(?:\.\d+)?', val_str)
        if num_match:
            try:
                num_val = float(num_match.group(0))
                if not (0.0 <= num_val <= 45.0):
                    answer.validated = False
                    answer.validation_error = f"Experience {num_val} years is outside valid range (0-45)"
                    return answer
            except ValueError:
                pass
        else:
            answer.validated = False
            answer.validation_error = f"Could not extract numeric experience from '{val_str}'"
            return answer

    # 4. Choice / Boolean Validation
    if available_options:
        opts_lower = [o.strip().lower() for o in available_options]
        if set(opts_lower) == {"yes", "no"}:
            if val_str.lower() not in ["yes", "no"]:
                answer.validated = False
                answer.validation_error = f"Boolean question requires 'Yes' or 'No', got '{val_str}'"
                return answer

    # 5. Non-empty string check
    if not val_str:
        answer.validated = False
        answer.validation_error = "Answer value cannot be empty"
        return answer

    answer.validated = True
    answer.validation_error = None
    return answer


class QnAEngine:
    def __init__(self, ai_client: Any = None):
        self.ai_client = ai_client
        self._reload_data()
        if self.ai_client is None:
            try:
                from app.services.ai_service import UniversalAIService
                self.set_universal_ai_service(UniversalAIService())
            except Exception:
                pass

    def _reload_data(self):
        self.personal = get_personal()
        self.prof = get_professional()
        self.qna = get_qna()
        self.ai_cfg = get_ai()

        self.custom_qa = dict(self.qna.get("custom_qa", {}))
        self.standard_answers = dict(self.qna.get("standard_answers", {}))
        self.ai_context = self.qna.get("ai_context", "")

        # Ingest verified entries from SQLite knowledge base
        try:
            from app.db.session import SessionLocal, get_db_session
            from app.db.models import QnAEntry
            with get_db_session(SessionLocal) as session:
                entries = (
                    session.query(QnAEntry)
                    .filter(QnAEntry.is_active == True, QnAEntry.validation_status != "REJECTED")  # noqa: E712
                    .all()
                )
                for e in entries:
                    if e.answer_text:
                        if e.normalized_question:
                            self.custom_qa[e.normalized_question] = e.answer_text
                        if e.question_text:
                            self.custom_qa[e.question_text] = e.answer_text
        except Exception:
            pass

        # Extract and cache candidate resume text for RAG
        self.resume_text = ""
        try:
            resume_path = self.prof.get("resume_path") or "PersonalData/Mohd_Ahmad_Raza_Ansari_Resume_11_09_2026.pdf"
            from pathlib import Path
            p = Path(resume_path)
            if not p.is_absolute():
                from modules.config_loader import _BASE_DIR
                p = _BASE_DIR / resume_path
            if p.exists() and p.suffix.lower() == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(str(p))
                self.resume_text = "\n".join([page.extract_text() or "" for page in reader.pages]).strip()
        except Exception:
            pass

        if self.resume_text and "RESUME CONTENT:" not in self.ai_context:
            self.full_ai_context = f"{self.ai_context}\n\nRESUME CONTENT:\n{self.resume_text[:4000]}"
        else:
            self.full_ai_context = self.ai_context

        # Pre-calculated compensation
        self.desired_salary = self.prof.get("desired_salary", 550000)
        self.current_ctc = self.prof.get("current_ctc", 350000)
        self.notice_period = self.prof.get("notice_period_days", 30)

        self.full_name = f"{self.personal.get('first_name', '')} {self.personal.get('middle_name', '')} {self.personal.get('last_name', '')}".replace("  ", " ").strip()

    def resolve_text_answer(
        self,
        question_label: str,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None,
    ) -> Answer:
        """Resolves text or textarea input questions with full answer provenance."""
        lbl = question_label.lower().strip()

        # Priority 1: Specific Unit conversions (Calculations)
        if any(w in lbl for w in ["ctc", "salary", "pay", "compensation"]):
            if any(u in lbl for u in ["lakh", "lac", "lpa"]):
                salary_val = self.current_ctc if any(w in lbl for w in ["current", "present"]) else self.desired_salary
                ans = Answer(value=f"{round(salary_val / 100000, 2):.2f}", source="calculation", confidence=0.98)
                return validate_answer(ans, question_label)
            if "month" in lbl:
                salary_val = self.current_ctc if any(w in lbl for w in ["current", "present"]) else self.desired_salary
                ans = Answer(value=str(round(salary_val / 12)), source="calculation", confidence=0.98)
                return validate_answer(ans, question_label)

        if "notice" in lbl and any(w in lbl for w in ["month", "week"]):
            if "month" in lbl:
                ans = Answer(value=str(max(1, self.notice_period // 30)), source="calculation", confidence=0.95)
            else:
                ans = Answer(value=str(max(1, self.notice_period // 7)), source="calculation", confidence=0.95)
            return validate_answer(ans, question_label)

        # Location preference keywords
        if "location" in lbl and any(w in lbl for w in ["prefer", "desir", "choice", "target", "work"]):
            if not any(w in lbl for w in ["current", "live"]):
                pref = str(self.standard_answers.get("preferred_location", "India (Open to Remote / Hybrid / Relocation)"))
                ans = Answer(value=pref, source="profile", confidence=1.0)
                return validate_answer(ans, question_label)

        # Priority 1b: Date of Birth / DOB (strict candidate profile identity)
        if any(w in lbl for w in ["dob", "date of birth", "birth date", "birthday", "born"]):
            dob_val = str(self.personal.get("date_of_birth") or self.personal.get("dob") or self.standard_answers.get("date_of_birth") or "15/05/2002")
            ans = Answer(value=dob_val, source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Priority 1c: Generic Overall Experience (strict candidate profile property)
        is_generic_overall = (
            lbl in ["years of experience", "total years of experience", "total experience", "overall experience", "total relevant experience"]
            or (
                any(t in lbl for t in ["total years of experience", "total experience", "overall experience", "total relevant experience"])
                and not any(s in lbl for s in [" in ", " with ", " on ", " using ", "api", "framework"])
            )
        )
        if is_generic_overall:
            exp_val = self.prof.get("years_of_experience", 2)
            try:
                f_exp = float(exp_val)
                exp_str = str(int(f_exp)) if f_exp.is_integer() else str(f_exp)
            except Exception:
                exp_str = str(exp_val)
            ans = Answer(value=exp_str, source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Priority 1d: Technology / Tools / Proficiency Lists
        is_tools_or_tech_list = (
            any(w in lbl for w in [
                "which tools", "which platforms", "which technologies",
                "what tools", "what technologies", "what platforms",
                "technologies are you proficient in", "tools are you proficient in", "platforms are you proficient in",
                "technologies you're proficient in", "tools you're proficient in",
                "primary technologies", "list the primary technologies", "technologies you've worked with",
                "technologies you have worked with", "tools you've worked with",
                "list all technologies", "tech stack", "tools/technologies",
                "tools and technologies", "skills and technologies"
            ])
            or (("proficient in" in lbl or "technologies" in lbl or "tools" in lbl) and any(w in lbl for w in ["list", "which", "what", "mention", "name"]))
        )
        if is_tools_or_tech_list and not any(w in lbl for w in ["how many years", "years of experience", "rate yourself"]):
            tech_list_ans = "Automation Anywhere 360, Python 3.11, SAP GUI Scripting, SQL, PostgreSQL, REST APIs, Git, GitHub, FastAPI, LangChain, OpenAI API, AWS Textract"
            ans = Answer(value=tech_list_ans, source="profile", confidence=0.98)
            return validate_answer(ans, question_label)

        # Priority 1e: Certifications / Training Programs
        if any(w in lbl for w in ["certifications", "training programs", "courses completed", "certified in"]) and not any(w in lbl for w in ["how many", "years of"]):
            if any(w in lbl for w in ["list", "what", "which", "name", "please"]):
                cert_ans = "Automation Anywhere Advanced Automation, Agentic Process Automation Developer Masterclass"
            else:
                cert_ans = "Yes, Automation Anywhere Advanced Automation and Agentic Automation Masterclass"
            ans = Answer(value=cert_ans, source="profile", confidence=0.98)
            return validate_answer(ans, question_label)

        # Priority 1f: Reason for Seeking New Opportunity / Career Change
        if any(w in lbl for w in ["reason for seeking", "seeking a new opportunity", "reason for change", "looking for a change", "reason for leaving", "why are you looking for"]):
            ans_reason = "Seeking new challenges in enterprise RPA and agentic AI automation."
            ans = Answer(value=ans_reason, source="profile", confidence=0.98)
            return validate_answer(ans, question_label)

        # Priority 1g: Why Do You Want to Join / Why This Company
        if any(w in lbl for w in ["why do you want to join", "why this company", "why our company", "why work with us"]):
            join_ans = "I am excited by your team's innovative engineering culture and technical vision. My background in Automation Anywhere, Python, and AI automation directly aligns with your objectives, and I am eager to contribute meaningfully."
            ans = Answer(value=join_ans, source="profile", confidence=0.98)
            return validate_answer(ans, question_label)

        # Priority 1h: Rating Scales (Scale of 1-5, 1-10)
        if any(w in lbl for w in ["scale of 1-5", "scale of 1 to 5", "scale (1-5)", "scale 1-5", "1-5 scale", "1 to 5 scale", "scale of 1 - 5", "scale of 1- 5"]):
            ans = Answer(value="4", source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["scale of 1-10", "scale of 1 to 10", "scale (1-10)", "scale 1-10", "1-10 scale", "1 to 10 scale", "scale of 1 - 10", "rate yourself"]):
            ans = Answer(value=str(self.prof.get("confidence_level", "9")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Priority 2: Custom Q&A Rule Bank
        is_descriptive = any(w in lbl for w in [
            "describe", "explain", "tell me", "detail", "overview", "elaborate",
            "how have you", "how did you", "what is your experience", "walk me through",
            "which tools", "which technologies", "what tools", "what technologies",
            "list", "mention", "proficient in", "primary technologies", "technologies you",
            "tools you", "tools, platforms", "frameworks", "libraries", "tech stack",
            "reason for", "why do you", "why should we", "certifications", "training programs"
        ])
        # Clean label by removing example parentheticals like (e.g., Jira, GitHub, ...) so examples do not falsely match short keys
        lbl_cleaned = re.sub(r'\(e\.?g\.?[^)]*\)', '', lbl)
        sorted_qa = sorted(self.custom_qa.items(), key=lambda item: len(item[0]), reverse=True)
        for key, val in sorted_qa:
            k_lower = key.lower().strip()
            if not k_lower:
                continue
            # For short 1-word keys (e.g. "git", "python", "sql", "github"), use word-boundary matching on cleaned label
            if len(k_lower.split()) <= 1:
                matched_key = bool(re.search(r'\b' + re.escape(k_lower) + r'\b', lbl_cleaned))
            else:
                matched_key = k_lower in lbl
            if matched_key:
                val_str = str(val).strip()
                if is_descriptive and (val_str.isdigit() or val_str.lower() in ["yes", "no"]):
                    continue
                ans = Answer(value=val_str, source="rule", confidence=0.92)
                return validate_answer(ans, question_label)

        # Location confirmation / based out of questions: "Are you based out of Bengaluru location?*"
        if any(p in lbl for p in ["are you based", "are you located", "do you reside", "currently based in", "currently located in", "based out of", "based in"]):
            if self.prof.get("willing_to_relocate", True) or "yes" in str(self.standard_answers.get("open_to_relocation", "")).lower():
                ans = Answer(value="Yes, open to relocate immediately.", source="profile", confidence=0.95)
            else:
                ans = Answer(value=f"No, currently based in {self.personal.get('current_city', 'Delhi')}", source="profile", confidence=0.9)
            return validate_answer(ans, question_label)

        # Qualitative / Yes-No Experience questions: "Do you have experience in the area of AI Agents / Bots / Gen AI?"
        is_qualitative_exp = (
            any(lbl.startswith(p) for p in ["do you have", "have you", "are you", "any experience", "describe", "explain", "please provide", "share"])
            or "do you have experience" in lbl
            or "have experience" in lbl
            or "experience in the area" in lbl
        )
        if is_qualitative_exp and ("experience" in lbl or "worked" in lbl or "knowledge" in lbl):
            candidate_corpus = f"{self.ai_context} {self.resume_text}".lower()
            skill_part = lbl
            for p in ["area of", "experience in", "experience with", "worked with"]:
                if p in lbl:
                    skill_part = lbl.split(p)[-1].replace("?", "").replace("*", "").strip()
                    break
            keywords = [k.strip() for k in re.split(r'[/,&\s]+', skill_part) if len(k.strip()) > 2 and k.strip() not in ["the", "and", "for", "with", "area", "domain"]]
            matched = any(k in candidate_corpus for k in keywords) if keywords else True
            if matched:
                ans_text = "Yes, 2 years of hands-on experience in this domain."
            else:
                ans_text = "Yes, strong foundational knowledge and fast learner."
            ans = Answer(value=ans_text, source="profile", confidence=0.95)
            return validate_answer(ans, question_label)

        # Priority 3: Standard Profile Rules

        # Experience: Distinguish overall experience vs skill-specific experience
        if any(w in lbl for w in ["experience", "years of exp", "how many years"]):
            # Check if this is asking for generic/total overall experience
            is_generic_overall = (
                lbl in ["years of experience", "total years of experience", "total experience", "overall experience", "total relevant experience"]
                or (
                    any(t in lbl for t in ["total years of experience", "total experience", "overall experience", "total relevant experience"])
                    and not any(s in lbl for s in [" in ", " with ", " on ", " using ", "api", "framework"])
                )
            )

            if is_generic_overall:
                exp_val = self.prof.get("years_of_experience", 2)
                try:
                    f_exp = float(exp_val)
                    exp_str = str(int(f_exp)) if f_exp.is_integer() else str(f_exp)
                except Exception:
                    exp_str = str(exp_val)
                ans = Answer(value=exp_str, source="profile", confidence=1.0)
                return validate_answer(ans, question_label)

            # Skill-specific experience question (e.g. "How many years of experience do you have in Solidworks Api?")
            # First, try AI query with candidate resume + profile RAG
            ai_ans = self._query_ai(question_label, job_description=job_description)
            if ai_ans:
                clean_ai = str(ai_ans).strip()
                m = re.search(r'\d+(?:\.\d+)?', clean_ai)
                if m:
                    clean_ai = m.group(0)
                self.save_learned_answer(question_label, clean_ai, category="skills", answer_type="number", source="llm")
                ans = Answer(value=clean_ai, source="llm", confidence=0.88)
                return validate_answer(ans, question_label)

            # If AI is unavailable, check if the skill name appears in candidate's resume/profile
            skill_name = ""
            for prep in [" in ", " with ", " on ", " using "]:
                if prep in lbl:
                    skill_name = lbl.split(prep)[-1].replace("?", "").strip()
                    break

            candidate_corpus = f"{self.ai_context} {self.resume_text}".lower()
            if skill_name and len(skill_name) > 1 and skill_name in candidate_corpus:
                exp_val = str(self.prof.get("years_of_experience", 2))
            elif skill_name and len(skill_name) > 1:
                # Skill explicitly not found in candidate resume or profile -> 0
                exp_val = "0"
            else:
                exp_val = str(self.prof.get("years_of_experience", 2))

            self.save_learned_answer(question_label, exp_val, category="skills", answer_type="number", source="rule")
            ans = Answer(value=exp_val, source="rule", confidence=0.75)
            return validate_answer(ans, question_label)

        # Personal details
        if "phone" in lbl or "mobile" in lbl:
            ans = Answer(value=str(self.personal.get("phone_number", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "email" in lbl:
            ans = Answer(value=str(self.personal.get("email", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "street" in lbl:
            ans = Answer(value=str(self.personal.get("street", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in [
            "current location", "your location", "current city", "city",
            "base location", "residing location", "present location",
            "where are you located", "where do you live", "where are you currently located",
            "your current location", "location where you are"
        ]) or (lbl.startswith("location") or lbl.endswith("location") or lbl == "location"):
            city = str(self.personal.get("current_city") or work_location or "Delhi")
            ans = Answer(value=city, source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        if "location" in lbl and not any(w in lbl for w in ["prefer", "desir", "choice", "target", "relocate", "relocation"]):
            city = str(self.personal.get("current_city") or work_location or "Delhi")
            ans = Answer(value=city, source="profile", confidence=0.95)
            return validate_answer(ans, question_label)

        if "state" in lbl or "province" in lbl:
            ans = Answer(value=str(self.personal.get("state", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["zip", "postal", "pincode"]):
            ans = Answer(value=str(self.personal.get("zipcode", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "country" in lbl:
            ans = Answer(value=str(self.personal.get("country", "India")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Name fields (specific first/middle/last checks MUST come before generic "name" check)
        if "first name" in lbl:
            ans = Answer(value=str(self.personal.get("first_name", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "middle name" in lbl:
            ans = Answer(value=str(self.personal.get("middle_name", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "last name" in lbl:
            ans = Answer(value=str(self.personal.get("last_name", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "signature" in lbl or "legal name" in lbl or "full name" in lbl or ("name" in lbl and "employer" not in lbl and "company" not in lbl):
            ans = Answer(value=self.full_name, source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Professional Links & Metadata
        if "linkedin" in lbl:
            ans = Answer(value=str(self.prof.get("linkedin_url", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["website", "portfolio", "github"]):
            ans = Answer(value=str(self.prof.get("portfolio_url", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["how did you hear", "hear about", "how did you learn", "learn about", "where did you hear", "where did you find", "referral source", "source of referral"]):
            ans = Answer(value="LinkedIn", source="rule", confidence=0.95)
            return validate_answer(ans, question_label)
        if "headline" in lbl:
            ans = Answer(value=str(self.prof.get("headline", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "employer" in lbl or "recent company" in lbl:
            ans = Answer(value=str(self.prof.get("current_employer", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "scale of 1-10" in lbl or "rate yourself" in lbl:
            ans = Answer(value=str(self.prof.get("confidence_level", "9")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Notice Period calculations
        if "notice" in lbl:
            if "month" in lbl:
                ans = Answer(value=str(max(1, self.notice_period // 30)), source="calculation", confidence=0.95)
            elif "week" in lbl:
                ans = Answer(value=str(max(1, self.notice_period // 7)), source="calculation", confidence=0.95)
            else:
                ans = Answer(value=str(self.notice_period), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Compensation calculations
        if any(w in lbl for w in ["salary", "compensation", "ctc", "expected", "desired", "pay"]):
            is_current = any(w in lbl for w in ["current", "present"])
            salary_val = self.current_ctc if is_current else self.desired_salary
            if any(u in lbl for u in ["lakh", "lac", "lpa"]):
                ans = Answer(value=f"{round(salary_val / 100000, 2):.2f}", source="calculation", confidence=0.98)
            elif "month" in lbl:
                ans = Answer(value=str(round(salary_val / 12)), source="calculation", confidence=0.98)
            else:
                ans = Answer(value=str(salary_val), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # Summary & Cover letter
        if "summary" in lbl or "about yourself" in lbl:
            ans = Answer(value=str(self.prof.get("summary", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if "cover" in lbl:
            ans = Answer(value=str(self.prof.get("cover_letter", "")), source="profile", confidence=1.0)
            return validate_answer(ans, question_label)

        # How did you hear
        if any(w in lbl for w in ["hear", "come across", "referral source"]):
            ans = Answer(value="LinkedIn", source="rule", confidence=0.9)
            return validate_answer(ans, question_label)

        # Location & Work Mode Preferences
        if any(w in lbl for w in ["preferred location", "desired location", "location preference"]):
            pref = str(self.standard_answers.get("preferred_location", "India (Open to Remote / Hybrid / Relocation)"))
            ans = Answer(value=pref, source="profile", confidence=1.0)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["willing to relocate", "open to relocate", "relocate"]):
            ans = Answer(value="Yes", source="rule", confidence=0.95)
            return validate_answer(ans, question_label)
        if any(w in lbl for w in ["remote", "work from home", "wfh", "hybrid"]):
            ans = Answer(value="Yes", source="rule", confidence=0.95)
            return validate_answer(ans, question_label)

        # Priority 4: AI Fallback based on user profile and resume data
        ai_ans = self._query_ai(question_label, job_description=job_description)
        if ai_ans:
            clean_ai = str(ai_ans).strip()
            self.save_learned_answer(question_label, clean_ai, category="ai_generated", answer_type="text", source="llm")
            ans = Answer(value=clean_ai, source="llm", confidence=0.85)
            return validate_answer(ans, question_label)

        # Context-aware fallback based on candidate data (never default to '2.0' for non-experience questions)
        if any(w in lbl for w in ["dob", "date of birth", "birth"]):
            ans_val = str(self.personal.get("date_of_birth") or self.personal.get("dob") or "15/05/2002")
        elif any(w in lbl for w in ["city", "location", "place", "address", "reside", "stay"]):
            ans_val = str(self.personal.get("current_city") or work_location or "Delhi")
        elif any(w in lbl for w in ["notice", "joining"]):
            ans_val = f"{self.notice_period} days"
        elif any(w in lbl for w in ["salary", "ctc", "lakh", "lac", "lpa"]):
            ans_val = f"{round(self.desired_salary / 100000, 2):.2f}"
        elif any(w in lbl for w in ["experience", "years"]):
            exp_val = self.prof.get("years_of_experience", 2)
            try:
                f_exp = float(exp_val)
                ans_val = str(int(f_exp)) if f_exp.is_integer() else str(f_exp)
            except Exception:
                ans_val = str(exp_val)
        elif any(w in lbl for w in ["ready", "willing", "authorized", "can you", "are you", "do you"]):
            ans_val = "Yes"
        elif any(w in lbl for w in ["name", "who are you"]):
            ans_val = self.full_name
        else:
            ans_val = str(self.prof.get("summary", "Experienced automation engineer with strong technical background."))

        self.save_learned_answer(question_label, ans_val, category="fallback", answer_type="text", source="fallback")
        ans = Answer(value=ans_val, source="profile", confidence=0.5)
        return validate_answer(ans, question_label)

    def answer_text_question(
        self,
        question_label: str,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None,
    ) -> str:
        """Backward-compatible string resolution."""
        ans = self.resolve_text_answer(question_label, job_description=job_description, work_location=work_location)
        return str(ans.value)

    def answer_question(
        self,
        question: str,
        options: Optional[List[str]] = None,
        field_type: str = "text",
        job_context: Optional[Dict[str, Any]] = None,
    ) -> Answer:
        """Universal question answering entry point with provenance."""
        if field_type in ["select", "radio", "choice"] or (options and len(options) > 0):
            ans, _ = self.resolve_choice_answer(question, available_options=options or [])
            return ans
        else:
            job_desc = job_context.get("description") if job_context else None
            work_loc = job_context.get("location") if job_context else None
            return self.resolve_text_answer(question, job_description=job_desc, work_location=work_loc)

    def resolve_choice_answer(
        self,
        question_label: str,
        available_options: List[str],
        work_location: Optional[str] = None,
    ) -> Tuple[Answer, Optional[str]]:
        """Determines target answer with provenance and selects best matching available option."""
        lbl = question_label.lower().strip()
        source: AnswerSource = "rule"
        confidence = 0.9
        target = "Yes"

        # Tier 1: Custom Q&A
        for key, val in self.custom_qa.items():
            if key.lower() in lbl:
                target = str(val)
                source = "rule"
                confidence = 0.95
                break
        else:
            # Tier 2: Standard rules
            source = "profile"
            confidence = 1.0
            if any(w in lbl for w in ["visa", "sponsorship"]):
                target = self.standard_answers.get("require_visa", "No")
            elif any(w in lbl for w in ["related to", "relative", "family member", "nepotism", "relationship with anyone", "conflict of interest"]):
                target = "No"
                source = "rule"
                confidence = 0.98
            elif any(w in lbl for w in ["ever worked for", "previously employed", "former employee", "previously worked", "prior employee", "worked at"]):
                target = "No"
                source = "rule"
                confidence = 0.98
            elif any(w in lbl for w in ["non-compete", "restrictive covenant", "disciplinary", "terminated", "fired", "convicted", "felony", "misdemeanor", "crime", "lawsuit", "sanctioned", "government official", "politically exposed"]):
                target = "No"
                source = "rule"
                confidence = 0.98
            elif any(w in lbl for w in ["citizenship", "authorized", "eligible to work"]):
                target = self.standard_answers.get("us_citizenship", "Other")
            elif "gender" in lbl or "sex" in lbl:
                target = self.personal.get("gender", "Male")
            elif "disability" in lbl:
                target = self.personal.get("disability_status", "No")
            elif any(w in lbl for w in ["veteran", "military", "armed forces", "served in", "served"]):
                vet_status = str(self.personal.get("veteran_status", "No")).lower().strip()
                if vet_status in ["no", "never", "none", "false", "0"]:
                    target = "Never served"
                else:
                    target = "Previously served"
            elif any(w in lbl for w in ["what service", "branch of service"]):
                target = "None"
            elif "ethnicity" in lbl or "race" in lbl:
                target = self.personal.get("ethnicity", "Asian")
            elif "proficiency" in lbl or "english" in lbl:
                target = "Professional"
                source = "rule"
            elif any(w in lbl for w in ["relocate", "relocation"]):
                target = self.standard_answers.get("open_to_relocation", "Yes")
            elif any(w in lbl for w in ["remote", "wfh", "work from home"]):
                target = self.standard_answers.get("comfortable_with_remote", "Yes")
            elif any(w in lbl for w in ["hybrid", "onsite", "on-site", "commute", "travel"]):
                target = "Yes"
                source = "rule"
            elif any(w in lbl for w in ["preferred location", "desired location"]):
                target = self.standard_answers.get("preferred_location", "India")
            elif any(w in lbl for w in ["phone country code", "country code", "dial code", "phone code"]):
                country_name = self.personal.get("country", "India")
                target = f"{country_name} (+91)" if country_name.lower() == "india" else country_name
            elif any(w in lbl for w in ["country", "state", "city"]):
                if "country" in lbl:
                    target = self.personal.get("country", "India")
                elif "state" in lbl:
                    target = self.personal.get("state", "Delhi")
                else:
                    target = self.personal.get("current_city", work_location or "Delhi")
            elif any(w in lbl for w in ["how did you hear", "hear about", "how did you learn", "learn about", "where did you hear", "where did you find", "referral source", "source of referral"]):
                target = "LinkedIn"
                source = "rule"
                confidence = 0.95
            else:
                target = "Yes"
                source = "rule"
                confidence = 0.6

        # Match target against available_options
        matched_option = self._match_option(target, available_options)
        if matched_option:
            target = matched_option

        # Tier 3: If no rule match, ask LLM based on user profile and available options
        if not matched_option and available_options:
            ai_choice = self._query_ai_select(question_label, available_options)
            if ai_choice:
                matched_option = ai_choice
                target = ai_choice
                source = "llm"
                confidence = 0.85
                self.save_learned_answer(question_label, str(ai_choice), category="choice", answer_type="choice", source="llm")
        elif not matched_option and available_options:
            # Fallback if no match: prefer negative for military/legal/crime, affirmative for skills
            if any(w in lbl for w in ["military", "veteran", "crime", "felony", "misdemeanor", "drug", "lawsuit"]):
                neg = self._match_option("No", available_options)
                if neg:
                    matched_option = neg
                    target = neg
            else:
                pos = self._match_option("Yes", available_options)
                if pos:
                    matched_option = pos
                    target = pos

        ans = Answer(
            value=target,
            source=source,
            confidence=confidence,
            field_type="select" if len(available_options) > 2 else "radio",
        )
        validated_ans = validate_answer(ans, question_label, available_options)
        # Auto-learn resolved question into QnA knowledge base if not already present
        if question_label and question_label.lower() not in [k.lower() for k in self.custom_qa]:
            self.save_learned_answer(question_label, str(validated_ans.value), category="choice", answer_type="choice", source=source)
        return validated_ans, matched_option

    def answer_select_or_radio(
        self,
        question_label: str,
        available_options: List[str],
        work_location: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Backward-compatible choice resolution."""
        ans, matched = self.resolve_choice_answer(question_label, available_options, work_location=work_location)
        return str(ans.value), matched

    def set_ai_client(self, ai_client: Any):
        self.ai_client = ai_client

    def set_universal_ai_service(self, ai_service: Any) -> bool:
        """Configures the QnAEngine's AI client from the Universal AI Service.

        Attempts to get an OpenAI-compatible client from UniversalAIService.get_active_client().
        Falls back to existing self.ai_client if the service cannot provide one.

        Returns:
            True if a new AI client was successfully set, False otherwise.
        """
        try:
            client = ai_service.get_active_client()
            if client:
                self.ai_client = client
                # Also update model from universal config
                cfg = ai_service.get_config()
                self.ai_cfg["model"] = cfg.get("model", self.ai_cfg.get("model", "llama3.1:8b"))
                return True
        except Exception:
            pass
        return False

    def _query_ai_select(self, question: str, options: List[str]) -> Optional[str]:
        if not options:
            return None
        try:
            clean_options = [opt.strip() for opt in options if opt.strip() and opt.strip().lower() != "select an option"]
            if not clean_options:
                return None
            opts_str = "\n".join([f"- {opt}" for opt in clean_options])
            prompt = (
                f"You are answering a job application question based on the candidate's profile.\n"
                f"Candidate Profile:\n{self.ai_context}\n\n"
                f"Question: {question}\n\n"
                f"Available Options:\n{opts_str}\n\n"
                f"Select the single best matching option from the list above.\n"
                f"Respond with ONLY the exact option text from the list, with no extra words, explanations, or quotes."
            )
            try:
                from app.services.ai_service import UniversalAIService
                svc = UniversalAIService()
                content = svc.generate_text(prompt, temperature=0.0).strip().strip('"\'')
                if content:
                    return self._match_option(content, clean_options)
            except Exception:
                pass

            if self.ai_client:
                cfg_model = self.ai_cfg.get("model", "llama3.1:8b")
                try:
                    response = self.ai_client.chat.completions.create(
                        model=cfg_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0
                    )
                    content = response.choices[0].message.content.strip().strip('"\'')
                    if content:
                        return self._match_option(content, clean_options)
                except Exception:
                    pass
            return None
        except Exception:
            return None

    def _match_option(self, target: str, options: List[str]) -> Optional[str]:
        if not options:
            return None

        # Filter out placeholder items like "Select an option", "Choose one", etc.
        placeholder_phrases = {
            "select an option", "select option", "select...", "select",
            "choose an option", "choose one", "choose...", "choose",
            "please select", "-- select --", "-- choose --", "none selected"
        }
        clean_options = [opt for opt in options if opt.strip() and opt.strip().lower() not in placeholder_phrases]
        pool = clean_options if clean_options else options

        target_lower = target.lower().strip()

        # 1. Exact match (case-insensitive)
        for opt in pool:
            if opt.strip().lower() == target_lower:
                return opt

        # 2. Direct bidirectional substring match
        for opt in pool:
            opt_lower = opt.strip().lower()
            if opt_lower in target_lower or target_lower in opt_lower:
                return opt

        # 3. Boolean / Confirmation matches
        if "yes" in target_lower:
            for opt in pool:
                if any(w in opt.lower() for w in ["yes", "agree", "i do", "i have", "authorized"]):
                    return opt
        elif any(neg in target_lower for neg in ["no", "never", "none"]):
            for opt in pool:
                if any(w in opt.lower() for w in [
                    "never served", "never", "none", "not applicable", "n/a",
                    "no", "disagree", "i do not", "i don't",
                    "neither", "not served", "no experience"
                ]):
                    return opt
        elif any(w in target_lower for w in ["decline", "prefer not", "not wish"]):
            for opt in pool:
                if any(w in opt.lower() for w in ["decline", "prefer not", "not wish", "don't wish", "do not wish"]):
                    return opt

        # 4. Token & Significant Entity Overlap (e.g. "I saw the job posting on LinkedIn" -> "LinkedIn")
        stopwords = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "by", "from", "i", "saw", "job", "posting", "post", "about", "this", "position",
            "opportunity", "heard", "learned", "found", "through", "via", "is", "was"
        }
        target_tokens = [w for w in re.findall(r'[a-zA-Z0-9]+', target_lower) if w not in stopwords]

        best_token_match = None
        best_token_score = 0
        for opt in pool:
            opt_lower = opt.lower()
            opt_tokens = [w for w in re.findall(r'[a-zA-Z0-9]+', opt_lower) if w not in stopwords]
            for tok in target_tokens:
                if len(tok) >= 3 and (tok in opt_lower or any(tok in ot for ot in opt_tokens)):
                    score = len(tok)
                    if score > best_token_score:
                        best_token_score = score
                        best_token_match = opt

        if best_token_match:
            return best_token_match

        # 5. Semantic Synonyms & Domain Category Mapping
        job_board_terms = ["linkedin", "indeed", "glassdoor", "naukri", "monster", "dice", "careerbuilder", "ziprecruiter"]
        if any(term in target_lower for term in job_board_terms):
            # Prefer other job board / professional platform options first (e.g. "LinkedIn" when target is "Indeed" or vice versa)
            for opt in pool:
                opt_l = opt.lower()
                if any(jb in opt_l for jb in job_board_terms) or any(j in opt_l for j in ["job board", "job site", "career portal", "online job"]):
                    return opt
            for opt in pool:
                opt_l = opt.lower()
                if any(j in opt_l for j in ["social media", "social network", "online", "internet", "portal"]):
                    return opt

        referral_terms = ["referral", "friend", "colleague", "coworker", "employee", "relative"]
        if any(term in target_lower for term in referral_terms):
            for opt in pool:
                opt_l = opt.lower()
                if any(r in opt_l for r in ["referral", "employee", "word of mouth", "internal", "friend"]):
                    return opt

        website_terms = ["company website", "career page", "career site", "company site"]
        if any(term in target_lower for term in website_terms):
            for opt in pool:
                opt_l = opt.lower()
                if any(w in opt_l for w in ["website", "career", "employer"]):
                    return opt

        # 6. Fuzzy Sequence Matching (difflib)
        import difflib
        best_ratio = 0.0
        best_ratio_opt = None
        for opt in pool:
            ratio = difflib.SequenceMatcher(None, target_lower, opt.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_ratio_opt = opt

        if best_ratio_opt and best_ratio >= 0.4:
            return best_ratio_opt

        # 7. Safe Fallback: Return first non-placeholder option so dropdown is never left unselected
        return pool[0] if pool else None

    def save_learned_answer(
        self,
        question: str,
        answer: str,
        category: str = "general",
        answer_type: str = "text",
        source: str = "auto_learned",
    ) -> bool:
        """Persists a new or unexpected question & answer into QnA knowledge base and config/profile.json."""
        q_clean = question.strip()
        a_clean = str(answer).strip()
        if not q_clean or not a_clean:
            return False

        # Guard: do not pollute custom_qa with core profile identity/experience/compensation fields
        # or garbage labels (e.g. 'Question', 'Option', or choice options masquerading as questions)
        q_lower = q_clean.lower()
        if len(q_clean) < 4 or q_lower in ("question", "option", "resume / cv upload", "upload resume", "save", "submit"):
            return False

        if "\n" in a_clean:
            return False

        if q_lower in ("currently serving", "previously served", "never served"):
            return False

        # Guard: only skip pure generic profile identity terms, NEVER skip skill-specific questions
        generic_terms = {
            "years of experience", "total years of experience", "total experience",
            "overall experience", "full name", "first name", "last name", "legal name",
            "phone", "mobile", "email", "current ctc", "expected ctc", "notice period",
            "dob", "date of birth", "birth date", "what is your dob", "what is you dob",
        }
        q_stripped = re.sub(r'[\?\:\*]', '', q_lower).strip()
        if q_stripped in generic_terms or any(w in q_lower for w in ["dob", "date of birth", "birth date"]):
            return False

        # 1. Update in-memory custom_qa
        self.custom_qa[q_clean] = a_clean

        # 2. Persist to config/profile.json
        try:
            import json
            from modules.config_loader import _PROFILE_PATH, load_profile
            prof = load_profile(force_reload=True)
            if "qna" not in prof:
                prof["qna"] = {}
            if "custom_qa" not in prof["qna"]:
                prof["qna"]["custom_qa"] = {}
            if q_clean not in prof["qna"]["custom_qa"]:
                prof["qna"]["custom_qa"][q_clean] = a_clean
                with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
                    json.dump(prof, f, indent=2)
                load_profile(force_reload=True)
        except Exception:
            pass

        # 3. Persist to SQLite QnAEntry via QnAService
        try:
            from app.services.qna_service import QnAService
            svc = QnAService()
            svc.add_entry(
                question=q_clean,
                answer=a_clean,
                category=category,
                answer_type=answer_type,
                source=source,
                confidence=0.85,
            )
        except Exception:
            pass

        return True

    def _query_ai(self, question: str, job_description: Optional[str] = None) -> Optional[str]:
        try:
            from modules.ai.prompts import ai_answer_prompt
            from modules.helpers import print_lg
            context = self.full_ai_context or self.ai_context or "N/A"
            prompt = ai_answer_prompt.format(context, question)
            if job_description and job_description != "Unknown":
                prompt += f"\nJob Description:\n{job_description}"

            # 1. Primary path: UniversalAIService (handles Ollama, Groq, xAI, NVIDIA, Gemini, etc.)
            try:
                from app.services.ai_service import UniversalAIService
                svc = UniversalAIService()
                txt = svc.generate_text(prompt, temperature=0.0).strip()
                if txt:
                    return txt
            except Exception as exc:
                print_lg(f"[QnAEngine] UniversalAIService query notice: {exc}")

            # 2. Legacy fallback: self.ai_client if configured
            if self.ai_client:
                cfg_model = self.ai_cfg.get("model", "llama3.1:8b")
                try:
                    response = self.ai_client.chat.completions.create(
                        model=cfg_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0
                    )
                    content = response.choices[0].message.content.strip()
                    if content:
                        return content
                except Exception as e:
                    print_lg(f"[QnAEngine] Legacy client query failed: {e}")
            return None
        except Exception as e:
            try:
                from modules.helpers import print_lg
                print_lg(f"[QnAEngine] AI query error for '{question}': {e}")
            except Exception:
                pass
            return None
