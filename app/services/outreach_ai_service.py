"""Guarded AI Email Draft Generation for Outreach Center."""

import json
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import sessionmaker

from app.db.models import Resume, User
from app.db.session import SessionLocal, get_db_session
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.ai_service import UniversalAIService
from app.services.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are JobPilot's specialized Recruiter Outreach Assistant.
Your task is to draft a concise, high-converting direct cold email from a job candidate to a hiring manager or recruiter.

STRICT GUARDRAILS:
1. ONLY reference skills, experience, and projects that appear in the candidate background. Do NOT hallucinate past employers, credentials, or skills.
2. Keep the email concise: between 90 and 150 words. Recruiters ignore long essays.
3. Be professional, direct, and respectful of their time.
4. Conclude with a low-friction call-to-action (e.g., a brief 10-minute introductory sync).
5. Output MUST be valid JSON with keys: "subject" and "body_text".
"""


class OutreachAIService:
    """Generates guarded, tailored cold outreach and follow-up drafts with template fallbacks."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        ai_service: Optional[UniversalAIService] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._ai_service = ai_service or UniversalAIService(session_factory=self._session_factory)

    def generate_pitch(
        self,
        company_name: str,
        job_title: str,
        recruiter_name: Optional[str] = None,
        resume_id: Optional[int] = None,
        tone: str = "direct",
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates a tailored email pitch using AI with a guaranteed template fallback."""
        recruiter = recruiter_name or "Hiring Team"
        cand_name = "Candidate"
        cand_skills = "Software Engineering, Python, Automation"

        cand_email = "candidate@example.com"
        yoe = "2"
        portfolio_url = ""

        with get_db_session(self._session_factory) as s:
            from app.repositories.user_repository import UserRepository
            repo = UserRepository(s)
            user = repo.get_primary_user()
            if user:
                cand_name = user.name or "Candidate"
                cand_email = user.email or cand_email
                pro = repo.get_professional_profile(user.id)
                if pro:
                    if pro.years_of_experience:
                        yoe = f"{pro.years_of_experience:.0f}"
                    if pro.skills:
                        cand_skills = ", ".join(pro.skills[:5]) if isinstance(pro.skills, list) else str(pro.skills)
                    if pro.portfolio_url:
                        portfolio_url = pro.portfolio_url
            if resume_id:
                resume = s.get(Resume, resume_id)
                if resume and resume.parsed_metadata and isinstance(resume.parsed_metadata, dict):
                    extracted_skills = resume.parsed_metadata.get("skills", [])
                    if extracted_skills:
                        cand_skills = ", ".join(extracted_skills[:6])

        # Attempt AI generation if configured
        try:
            cfg = self._ai_service.get_config()
            if cfg.get("enabled"):
                custom_text = f"\nSpecific Candidate Instructions: {custom_instructions.strip()}\n" if custom_instructions and custom_instructions.strip() else ""
                prompt = (
                    f"Candidate Name: {cand_name}\n"
                    f"Candidate Skills: {cand_skills}\n"
                    f"Years of Experience: {yoe}\n"
                    f"Target Company: {company_name}\n"
                    f"Target Position: {job_title}\n"
                    f"Recruiter Name: {recruiter}\n"
                    f"Tone: {tone}\n"
                    f"{custom_text}\n"
                    f"Draft a cold application email following all guardrails."
                )

                result_json = self._ai_service.extract_structured_json(
                    prompt=prompt,
                    schema_description='{"subject": "string", "body_text": "string"}',
                    system_prompt=SYSTEM_PROMPT,
                )

                if result_json and result_json.get("subject") and result_json.get("body_text"):
                    return {
                        "source": "ai",
                        "subject": result_json["subject"].strip(),
                        "body_text": result_json["body_text"].strip(),
                    }
        except Exception as e:
            logger.warning("AI generation unavailable or failed: %s. Using template fallback.", e)

        # Fallback to canonical template
        with get_db_session(self._session_factory) as s:
            tmpl_repo = EmailTemplateRepository(s)
            tmpl_repo.seed_defaults_if_empty()
            tmpl = tmpl_repo.get_by_key("direct_application_pitch")
            ctx = {
                "candidate_name": cand_name,
                "candidate_email": cand_email,
                "recruiter_name": recruiter,
                "company_name": company_name,
                "job_title": job_title,
                "skills": cand_skills,
                "years_of_experience": yoe,
                "portfolio_url": portfolio_url,
            }
            subj, _ = TemplateRenderer.render(tmpl.subject_template, ctx, strict=False)
            body, _ = TemplateRenderer.render(tmpl.body_template, ctx, strict=False)

            return {
                "source": "template_fallback",
                "subject": subj,
                "body_text": body,
            }

    def refine_pitch(
        self,
        current_body: str,
        instructions: Optional[str] = None,
        company_name: str = "",
        job_title: str = "",
    ) -> Dict[str, Any]:
        """Refines existing draft email body based on user prompts or polish heuristics."""
        clean_body = (current_body or "").strip()
        if not clean_body:
            return {"body_text": "", "source": "empty"}

        user_req = (instructions or "Improve clarity, tone, and conciseness while keeping it professional.").strip()

        try:
            cfg = self._ai_service.get_config()
            if cfg.get("enabled"):
                system_prompt = (
                    "You are JobPilot's specialized email refinement copilot.\n"
                    "Refine and polish the candidate's email draft according to their instructions.\n"
                    "Maintain the candidate's core voice and facts. Keep it concise (under 150 words).\n"
                    "Return ONLY the refined email text with no commentary or quotes."
                )
                prompt = (
                    f"Target Company: {company_name or 'N/A'}\n"
                    f"Target Position: {job_title or 'N/A'}\n"
                    f"Refinement Instructions: {user_req}\n\n"
                    f"Current Draft Body:\n{clean_body}\n\n"
                    f"Refined Body:"
                )
                refined = self._ai_service.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                )
                if refined and refined.strip():
                    return {
                        "body_text": refined.strip(),
                        "source": "ai",
                    }
        except Exception as e:
            logger.warning("AI refine failed: %s", e)

        # Fallback: clean up whitespace
        return {
            "body_text": clean_body,
            "source": "fallback",
        }

    def generate_rag_reply(
        self,
        application_id: int,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates a RAG-grounded contextual reply to a recruiter thread using full history and profile facts."""
        from sqlalchemy import select
        from app.db.models import Application, Communication, Job, User, Profile, ProfessionalProfile
        from app.repositories.user_repository import UserRepository

        cand_name = "Candidate"
        cand_email = ""
        cand_phone = ""
        cand_city = "Delhi"
        yoe = "2"
        notice_days = "30"
        expected_ctc = ""
        skills = ""
        company_name = ""
        job_title = ""
        recruiter_name = "Recruiter"
        history_lines = []

        with get_db_session(self._session_factory) as s:
            app = s.get(Application, application_id)
            if app:
                if app.job:
                    job_title = app.job.title or ""
                    company_name = getattr(app.job, "company_raw", None) or (app.job.company.name if app.job.company else "")
                if app.contact and app.contact.name:
                    recruiter_name = app.contact.name

                comms = s.execute(
                    select(Communication)
                    .where(Communication.application_id == application_id)
                    .order_by(Communication.occurred_at.asc(), Communication.id.asc())
                ).scalars().all()

                for c in comms:
                    sender = f"Recruiter ({c.sender_email or recruiter_name})" if c.direction == "INBOUND" else "You (Candidate)"
                    body = (c.body_snippet or "").strip()
                    if body:
                        history_lines.append(f"{sender}:\n{body}")

            user_repo = UserRepository(s)
            u = user_repo.get_primary_user()
            if u:
                cand_name = u.name or cand_name
                cand_email = u.email or ""
                cand_phone = u.phone or ""
                prof = user_repo.get_profile(u.id)
                pro = user_repo.get_professional_profile(u.id)
                if prof and getattr(prof, "current_city", None):
                    cand_city = prof.current_city
                if pro:
                    if pro.years_of_experience:
                        yoe = f"{pro.years_of_experience:.1f} years"
                    if getattr(pro, "notice_period_days", None):
                        notice_days = f"{pro.notice_period_days} days"
                    if getattr(pro, "expected_salary", None) or getattr(pro, "expected_ctc", None):
                        val = getattr(pro, "expected_ctc", None) or getattr(pro, "expected_salary", None)
                        expected_ctc = str(val)
                    if pro.skills:
                        skills = ", ".join(pro.skills[:8]) if isinstance(pro.skills, list) else str(pro.skills)

        formatted_history = "\n\n".join(history_lines) if history_lines else "No previous messages recorded in thread."

        try:
            cfg = self._ai_service.get_config()
            if cfg.get("enabled"):
                system_prompt = (
                    "You are JobPilot's specialized Recruitment Email Copilot.\n"
                    "Your task is to draft a natural, direct, highly professional email reply to the recruiter.\n"
                    "GROUND TRUTH RULES:\n"
                    "1. Accurately answer any specific questions the recruiter asked (e.g. experience, contact info, notice period, CTC) using the candidate profile facts below.\n"
                    "2. Do NOT invent or hallucinate facts not provided in Candidate Facts.\n"
                    "3. Adhere strictly to the candidate's custom instructions if provided.\n"
                    "4. Keep the reply concise (under 120 words), polite, and formatted as an email body.\n"
                    "5. Return ONLY the reply email body text. Do not include subject line or meta explanations."
                )

                user_req_text = f"Candidate's Custom Reply Instructions: {user_prompt.strip()}\n" if user_prompt and user_prompt.strip() else ""

                prompt = (
                    f"Recruiter: {recruiter_name} at {company_name or 'Company'}\n"
                    f"Position: {job_title or 'Target Role'}\n\n"
                    f"--- CONVERSATION HISTORY ---\n"
                    f"{formatted_history}\n\n"
                    f"--- CANDIDATE GROUND TRUTH FACTS ---\n"
                    f"Name: {cand_name}\n"
                    f"Email: {cand_email}\n"
                    f"Phone Number: {cand_phone}\n"
                    f"City/Location: {cand_city}\n"
                    f"Years of Experience: {yoe}\n"
                    f"Notice Period: {notice_days}\n"
                    f"Expected CTC: {expected_ctc or 'Competitive / Negotiable'}\n"
                    f"Core Skills: {skills}\n\n"
                    f"{user_req_text}"
                    f"Draft the reply email body now:"
                )

                reply_text = self._ai_service.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                )
                if reply_text and reply_text.strip():
                    return {
                        "body_text": reply_text.strip(),
                        "source": "ai_rag",
                    }
        except Exception as e:
            logger.warning("RAG reply generation failed: %s", e)

        # High-quality fallback answering typical recruiter screening queries
        fallback_reply = (
            f"Hi {recruiter_name},\n\n"
            f"Thank you for getting back to me! To answer your question:\n"
            f"I have {yoe} of hands-on experience in {skills or 'software engineering'}. "
            f"{f'You can reach me directly on mobile at {cand_phone} or via this email. ' if cand_phone else ''}"
            f"My notice period is {notice_days}.\n\n"
            f"I look forward to discussing the role further!\n\n"
            f"Best regards,\n{cand_name}"
        )
        return {
            "body_text": fallback_reply,
            "source": "rag_fallback",
        }

    def classify_response(
        self,
        email_body: str,
        email_subject: str = "",
    ) -> Dict[str, Any]:
        """Categorizes incoming recruiter email into InboundClassification with confidence and suggested actions.

        Uses LLM with strict JSON schema if available, falling back to deterministic keyword heuristics.
        """
        raw_text = f"{email_subject}\n{email_body}".strip()
        if not raw_text:
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "rationale_snippet": "Empty message content",
                "suggested_action": "NONE",
                "source": "heuristic_rules",
            }

        # 1. Attempt LLM classification if configured
        try:
            cfg = self._ai_service.get_config()
            if cfg.get("enabled"):
                prompt = (
                    f"Email Subject: {email_subject}\n"
                    f"Email Body:\n{email_body[:2000]}\n\n"
                    f"Classify this email response from a recruiter or hiring team into EXACTLY ONE of the categories:\n"
                    f"- INTERVIEW_REQUEST (requests call, screen, meeting, interview)\n"
                    f"- ASSESSMENT_REQUEST (coding challenge, test, task)\n"
                    f"- REJECTION (declines application, not moving forward)\n"
                    f"- OFFER (formal or informal job offer)\n"
                    f"- INFORMATION_REQUEST (asks for salary, notice period, portfolio)\n"
                    f"- ACKNOWLEDGEMENT (automated receipt confirmation)\n"
                    f"- OTHER\n"
                )
                system_prompt = (
                    "You are an expert recruiter correspondence classifier for JobPilot.\n"
                    "Analyze the text objectively and return JSON with keys:\n"
                    '"category" (one of INTERVIEW_REQUEST, ASSESSMENT_REQUEST, REJECTION, OFFER, INFORMATION_REQUEST, ACKNOWLEDGEMENT, OTHER),\n'
                    '"confidence" (HIGH, MEDIUM, LOW),\n'
                    '"rationale_snippet" (one-sentence reason),\n'
                    '"suggested_action" (one of INTERVIEW, ASSESSMENT, REJECTED, OFFER, REPLY, NONE).'
                )

                result_json = self._ai_service.extract_structured_json(
                    prompt=prompt,
                    schema_description='{"category": "string", "confidence": "string", "rationale_snippet": "string", "suggested_action": "string"}',
                    system_prompt=system_prompt,
                )

                if result_json and result_json.get("category"):
                    cat = result_json["category"].strip().upper()
                    valid_categories = {
                        "INTERVIEW_REQUEST", "ASSESSMENT_REQUEST", "REJECTION",
                        "OFFER", "INFORMATION_REQUEST", "ACKNOWLEDGEMENT", "OTHER",
                    }
                    if cat in valid_categories:
                        return {
                            "category": cat,
                            "confidence": result_json.get("confidence", "HIGH").upper(),
                            "rationale_snippet": result_json.get("rationale_snippet", "Classified by AI model"),
                            "suggested_action": result_json.get("suggested_action", "NONE").upper(),
                            "source": "ai",
                        }
        except Exception as e:
            logger.warning("AI classification failed or unavailable: %s. Using heuristic classifier.", e)

        # 2. Deterministic Rule-Based Heuristics
        lower = raw_text.lower()

        # Check Offer
        offer_terms = ["offer letter", "pleased to offer", "job offer", "congratulations on the offer", "compensation package"]
        if any(term in lower for term in offer_terms):
            return {
                "category": "OFFER",
                "confidence": "HIGH",
                "rationale_snippet": "Email explicitly references a job offer or compensation package",
                "suggested_action": "OFFER",
                "source": "heuristic_rules",
            }

        # Check Interview
        interview_terms = [
            "interview", "schedule a call", "phone screen", "introductory chat",
            "chat with the team", "availability for a", "next round", "discuss your background",
            "zoom call", "google meet", "teams meeting", "calendly.com", "calendar link",
        ]
        if any(term in lower for term in interview_terms):
            return {
                "category": "INTERVIEW_REQUEST",
                "confidence": "HIGH",
                "rationale_snippet": "Email invites or requests availability for an interview or discussion",
                "suggested_action": "INTERVIEW",
                "source": "heuristic_rules",
            }

        # Check Assessment
        assessment_terms = [
            "coding test", "hackerrank", "take-home", "take home", "online assessment",
            "coding challenge", "technical assessment", "screening test",
        ]
        if any(term in lower for term in assessment_terms):
            return {
                "category": "ASSESSMENT_REQUEST",
                "confidence": "HIGH",
                "rationale_snippet": "Email requests completion of a technical test or assessment",
                "suggested_action": "ASSESSMENT",
                "source": "heuristic_rules",
            }

        # Check Rejection
        rejection_terms = [
            "unfortunately", "not moving forward", "moved forward with another",
            "moving forward with other candidates", "decided not to proceed",
            "wish you the best in your search", "not a match at this time",
            "other candidates whose qualifications", "cannot offer you an interview",
        ]
        if any(term in lower for term in rejection_terms):
            return {
                "category": "REJECTION",
                "confidence": "HIGH",
                "rationale_snippet": "Email communicates that application is not proceeding",
                "suggested_action": "REJECTED",
                "source": "heuristic_rules",
            }

        # Check Information Request
        info_terms = [
            "notice period", "current ctc", "expected ctc", "compensation expectations",
            "share your updated resume", "portfolio link", "work authorization",
            "visa sponsorship", "years of experience in",
        ]
        if any(term in lower for term in info_terms):
            return {
                "category": "INFORMATION_REQUEST",
                "confidence": "MEDIUM",
                "rationale_snippet": "Recruiter is requesting specific candidate details or screening answers",
                "suggested_action": "REPLY",
                "source": "heuristic_rules",
            }

        # Check Acknowledgement
        ack_terms = [
            "thank you for your interest", "received your application",
            "we have received", "application received", "review your application",
            "automated message", "do not reply to this email",
        ]
        if any(term in lower for term in ack_terms):
            return {
                "category": "ACKNOWLEDGEMENT",
                "confidence": "MEDIUM",
                "rationale_snippet": "Automated receipt or generic application acknowledgement",
                "suggested_action": "NONE",
                "source": "heuristic_rules",
            }

        # Generic Recruiter Response
        return {
            "category": "RECRUITER_RESPONSE",
            "confidence": "LOW",
            "rationale_snippet": "Direct message received from recruiter, manual review recommended",
            "suggested_action": "REPLY",
            "source": "heuristic_rules",
        }

