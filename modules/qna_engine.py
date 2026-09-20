'''
Unified QnA Engine
Intelligent, multi-tier question answering for job applications across platforms.
'''

import re
from typing import List, Optional, Tuple, Any, Dict
from modules.config_loader import get_personal, get_professional, get_qna, get_ai

class QnAEngine:
    def __init__(self, ai_client: Any = None):
        self.ai_client = ai_client
        self._reload_data()

    def _reload_data(self):
        self.personal = get_personal()
        self.prof = get_professional()
        self.qna = get_qna()
        self.ai_cfg = get_ai()

        self.custom_qa = self.qna.get("custom_qa", {})
        self.standard_answers = self.qna.get("standard_answers", {})
        self.ai_context = self.qna.get("ai_context", "")

        # Pre-calculated compensation
        self.desired_salary = self.prof.get("desired_salary", 1200000)
        self.current_ctc = self.prof.get("current_ctc", 700000)
        self.notice_period = self.prof.get("notice_period_days", 30)

        self.full_name = f"{self.personal.get('first_name', '')} {self.personal.get('middle_name', '')} {self.personal.get('last_name', '')}".replace("  ", " ").strip()

    def answer_text_question(
        self,
        question_label: str,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None
    ) -> str:
        """Resolves text or textarea input questions."""
        lbl = question_label.lower().strip()

        # Priority: Specific CTC unit conversions (lakhs / months)
        if any(w in lbl for w in ["ctc", "salary", "pay", "compensation"]):
            if "lakh" in lbl:
                salary_val = self.current_ctc if any(w in lbl for w in ["current", "present"]) else self.desired_salary
                return f"{round(salary_val / 100000, 2):.2f}"
            if "month" in lbl:
                salary_val = self.current_ctc if any(w in lbl for w in ["current", "present"]) else self.desired_salary
                return str(round(salary_val / 12))

        # Location preference keywords
        if "location" in lbl and any(w in lbl for w in ["prefer", "desir", "choice", "target", "work"]):
            if any(w in lbl for w in ["current", "live"]):
                pass # let it be handled by current location rule below
            else:
                return str(self.standard_answers.get("preferred_location", "India (Open to Remote / Hybrid / Relocation)"))

        # Tier 1: Custom Q&A Bank
        is_descriptive = any(w in lbl for w in ["describe", "explain", "tell me", "detail", "overview", "elaborate", "how have you", "how did you", "what is your experience", "walk me through"])
        
        # Check longer and more specific keys first
        sorted_qa = sorted(self.custom_qa.items(), key=lambda item: len(item[0]), reverse=True)
        for key, val in sorted_qa:
            if key.lower() in lbl:
                val_str = str(val).strip()
                # If question is asking to describe or explain, skip pure numeric or boolean answers
                if is_descriptive and (val_str.isdigit() or val_str.lower() in ["yes", "no"]):
                    continue
                return val_str

        # Tier 2: Standard Rule Matches
        # Experience
        if any(w in lbl for w in ["experience", "years of exp", "how many years"]):
            return str(self.prof.get("years_of_experience", 2))

        # Personal details
        if "phone" in lbl or "mobile" in lbl:
            return str(self.personal.get("phone_number", ""))
        if "email" in lbl:
            return str(self.personal.get("email", ""))
        if "street" in lbl:
            return str(self.personal.get("street", ""))
        if any(w in lbl for w in ["city", "current location"]):
            return str(self.personal.get("current_city", work_location or ""))
        if "state" in lbl or "province" in lbl:
            return str(self.personal.get("state", ""))
        if any(w in lbl for w in ["zip", "postal", "pincode"]):
            return str(self.personal.get("zipcode", ""))
        if "country" in lbl:
            return str(self.personal.get("country", "India"))

        # Name fields
        if "signature" in lbl or "legal name" in lbl:
            return self.full_name
        if "first name" in lbl:
            return str(self.personal.get("first_name", ""))
        if "last name" in lbl:
            return str(self.personal.get("last_name", ""))
        if "middle name" in lbl:
            return str(self.personal.get("middle_name", ""))
        if "name" in lbl and "employer" not in lbl and "company" not in lbl:
            return self.full_name

        # Professional Links & Metadata
        if "linkedin" in lbl:
            return str(self.prof.get("linkedin_url", ""))
        if any(w in lbl for w in ["website", "portfolio", "github"]):
            return str(self.prof.get("portfolio_url", ""))
        if "headline" in lbl:
            return str(self.prof.get("headline", ""))
        if "employer" in lbl or "recent company" in lbl:
            return str(self.prof.get("current_employer", ""))
        if "scale of 1-10" in lbl or "rate yourself" in lbl:
            return str(self.prof.get("confidence_level", "9"))

        # Notice Period calculations
        if "notice" in lbl:
            if "month" in lbl:
                return str(max(1, self.notice_period // 30))
            if "week" in lbl:
                return str(max(1, self.notice_period // 7))
            return str(self.notice_period)

        # Compensation calculations
        if any(w in lbl for w in ["salary", "compensation", "ctc", "expected", "desired", "pay"]):
            is_current = any(w in lbl for w in ["current", "present"])
            salary_val = self.current_ctc if is_current else self.desired_salary
            if "lakh" in lbl:
                return f"{round(salary_val / 100000, 2):.2f}"
            if "month" in lbl:
                return str(round(salary_val / 12))
            return str(salary_val)

        # Summary & Cover letter
        if "summary" in lbl or "about yourself" in lbl:
            return str(self.prof.get("summary", ""))
        if "cover" in lbl:
            return str(self.prof.get("cover_letter", ""))

        # How did you hear
        if any(w in lbl for w in ["hear", "come across", "referral source"]):
            return "LinkedIn"

        # Location & Work Mode Preferences
        if any(w in lbl for w in ["preferred location", "desired location", "location preference"]):
            return str(self.standard_answers.get("preferred_location", "India (Open to Remote / Hybrid / Relocation)"))
        if any(w in lbl for w in ["willing to relocate", "open to relocate", "relocate"]):
            return "Yes"
        if any(w in lbl for w in ["remote", "work from home", "wfh", "hybrid"]):
            return "Yes"

        # Tier 3: AI Fallback
        if self.ai_client and self.ai_cfg.get("enabled", False):
            ai_ans = self._query_ai(question_label, job_description=job_description)
            if ai_ans:
                return ai_ans

        # Tier 4: Safe default
        return str(self.prof.get("years_of_experience", 2))

    def answer_select_or_radio(
        self,
        question_label: str,
        available_options: List[str],
        work_location: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Determines the target answer and finds the best matching available option text.
        Returns: (target_answer, matched_option_text_or_None)
        """
        lbl = question_label.lower().strip()
        target = "Yes"

        # Tier 1: Custom Q&A
        for key, val in self.custom_qa.items():
            if key.lower() in lbl:
                target = str(val)
                break
        else:
            # Tier 2: Standard rules
            if any(w in lbl for w in ["visa", "sponsorship"]):
                target = self.standard_answers.get("require_visa", "No")
            elif any(w in lbl for w in ["citizenship", "authorized", "eligible to work"]):
                target = self.standard_answers.get("us_citizenship", "Other")
            elif "gender" in lbl or "sex" in lbl:
                target = self.personal.get("gender", "Male")
            elif "disability" in lbl:
                target = self.personal.get("disability_status", "No")
            elif "veteran" in lbl:
                target = self.personal.get("veteran_status", "No")
            elif "ethnicity" in lbl or "race" in lbl:
                target = self.personal.get("ethnicity", "Asian")
            elif "proficiency" in lbl or "english" in lbl:
                target = "Professional"
            elif any(w in lbl for w in ["relocate", "relocation"]):
                target = self.standard_answers.get("open_to_relocation", "Yes")
            elif any(w in lbl for w in ["remote", "wfh", "work from home"]):
                target = self.standard_answers.get("comfortable_with_remote", "Yes")
            elif any(w in lbl for w in ["hybrid", "onsite", "on-site", "commute", "travel"]):
                target = "Yes"
            elif any(w in lbl for w in ["preferred location", "desired location"]):
                target = self.standard_answers.get("preferred_location", "India")
            elif any(w in lbl for w in ["country", "state", "city"]):
                if "country" in lbl: target = self.personal.get("country", "India")
                elif "state" in lbl: target = self.personal.get("state", "Delhi")
                else: target = self.personal.get("current_city", work_location or "Delhi")

        # Match target against available_options
        matched_option = self._match_option(target, available_options)

        # Tier 3: If no match and AI enabled, ask LLM to pick the best option
        if not matched_option and self.ai_client and self.ai_cfg.get("enabled", False) and available_options:
            ai_choice = self._query_ai_select(question_label, available_options)
            if ai_choice:
                matched_option = ai_choice
                target = ai_choice

        return target, matched_option

    def set_ai_client(self, ai_client: Any):
        """Sets or updates the AI client instance."""
        self.ai_client = ai_client

    def _query_ai_select(self, question: str, options: List[str]) -> Optional[str]:
        """Ask LLM to choose the single best option from a list of options."""
        if not self.ai_client or not options:
            return None
        try:
            # Filter out empty options or placeholders like 'Select an option'
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
            model = self.ai_cfg.get("model", "llama3.1:8b")
            response = self.ai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = response.choices[0].message.content.strip().strip('"\'')
            return self._match_option(content, clean_options)
        except Exception:
            return None

    def _match_option(self, target: str, options: List[str]) -> Optional[str]:
        """Fuzzy and case-insensitive option matcher."""
        target_lower = target.lower().strip()
        
        # 1. Exact match
        for opt in options:
            if opt.strip().lower() == target_lower:
                return opt

        # 2. Substring match
        for opt in options:
            opt_lower = opt.strip().lower()
            if target_lower in opt_lower or opt_lower in target_lower:
                return opt

        # 3. Synonyms / Semantic mapping
        if "yes" in target_lower:
            for opt in options:
                if any(w in opt.lower() for w in ["yes", "agree", "i do", "i have", "authorized"]):
                    return opt
        elif "no" in target_lower:
            for opt in options:
                if any(w in opt.lower() for w in ["no", "disagree", "i do not", "i don't"]):
                    return opt
        elif "decline" in target_lower:
            for opt in options:
                if any(w in opt.lower() for w in ["decline", "prefer not", "not wish", "don't wish"]):
                    return opt

        return None

    def _query_ai(self, question: str, job_description: Optional[str] = None) -> Optional[str]:
        """Queries local Ollama or OpenAI provider for novel questions."""
        try:
            from modules.ai.prompts import ai_answer_prompt
            prompt = ai_answer_prompt.format(self.ai_context or "N/A", question)
            if job_description and job_description != "Unknown":
                prompt += f"\nJob Description:\n{job_description}"

            model = self.ai_cfg.get("model", "llama3.1:8b")
            response = self.ai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = response.choices[0].message.content.strip()
            return content if content else None
        except Exception:
            return None
