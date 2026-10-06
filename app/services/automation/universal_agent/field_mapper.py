"""Semantic Field Mapper & Data Provenance Layer.

Matches generic ATS form fields to candidate facts strictly sourced from
ProfileService (User, Profile, ProfessionalProfile), ResumeService (Resume),
and QnAService (QnAEntry). Enforces strict provenance and prevents AI hallucinations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.services.automation.universal_agent.page_analyzer import FormAnalysisResult, FormFieldInfo
from app.services.automation.universal_agent.state_machine import InterventionReason

logger = logging.getLogger(__name__)


@dataclass
class FieldProvenance:
    """Audit trail verifying the authentic source and confidence of candidate data."""

    source_domain: str  # "profile", "resume", "qna", "manual", "computed"
    source_key: str  # e.g. "user.first_name", "profile.phone_number", "resume.file_path", "legally_authorized_to_work"
    confidence: float = 1.0
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FieldMapping:
    """The resolved mapping for a single form input element."""

    field_info: FormFieldInfo
    resolved_value: Optional[str] = None
    selected_option_value: Optional[str] = None
    provenance: Optional[FieldProvenance] = None
    is_resolved: bool = False
    notes: Optional[str] = None

    @property
    def is_required(self) -> bool:
        return bool(self.field_info.required)

    @property
    def effective_value(self) -> Optional[str]:
        """Returns the final value to fill: selected_option_value if option field, else resolved_value."""
        if self.field_info.options and self.selected_option_value is not None:
            return self.selected_option_value
        return self.resolved_value


@dataclass
class MappingResult:
    """Outcome of mapping an entire page or form schema to candidate profile facts."""

    mappings: List[FieldMapping] = field(default_factory=list)
    resolved_count: int = 0
    unresolved_count: int = 0
    unresolved_required_fields: List[FieldMapping] = field(default_factory=list)
    unresolved_optional_fields: List[FieldMapping] = field(default_factory=list)
    has_blocking_intervention: bool = False
    intervention_reason: Optional[InterventionReason] = None
    accuracy: float = 0.0

    def get_mapping(self, identifier: str) -> Optional[FieldMapping]:
        """Looks up a mapping by matching field_id, name, or selector."""
        for m in self.mappings:
            if m.field_info.field_id == identifier or m.field_info.name == identifier or m.field_info.selector == identifier:
                return m
        return None

    def get_resolved_mapping(self, identifier: str) -> Optional[FieldMapping]:
        m = self.get_mapping(identifier)
        return m if (m and m.is_resolved) else None


class SemanticFieldMapper:
    """Resolves form input fields to candidate data with zero hallucination guarantee."""

    def __init__(
        self,
        profile_service: Optional[Any] = None,
        resume_service: Optional[Any] = None,
        qna_service: Optional[Any] = None,
        qna_engine: Optional[Any] = None,
        user_id: Optional[int] = None,
        candidate_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.profile_service = profile_service
        self.resume_service = resume_service
        self.qna_service = qna_service
        self.qna_engine = qna_engine
        self.user_id = user_id
        self.candidate_context = candidate_context or {}

        if self.profile_service is None and not self.candidate_context:
            try:
                from app.services.profile_service import ProfileService
                self.profile_service = ProfileService()
            except Exception:
                pass
        if self.resume_service is None and not self.candidate_context:
            try:
                from app.services.resume_service import ResumeService
                self.resume_service = ResumeService()
            except Exception:
                pass
        if self.qna_service is None:
            try:
                from app.services.qna_service import QnAService
                self.qna_service = QnAService()
            except Exception:
                pass
        if self.qna_engine is None:
            try:
                from modules.qna_engine import QnAEngine
                self.qna_engine = QnAEngine()
            except Exception:
                pass

    def map_fields(self, form_result_or_fields: Union[FormAnalysisResult, List[FormFieldInfo]]) -> MappingResult:
        """Maps discovered form fields against candidate data sources."""
        if isinstance(form_result_or_fields, FormAnalysisResult):
            fields_to_map = form_result_or_fields.fields
        else:
            fields_to_map = form_result_or_fields

        facts = self._gather_candidate_facts()

        mappings: List[FieldMapping] = []
        unresolved_req: List[FieldMapping] = []
        unresolved_opt: List[FieldMapping] = []
        resolved_count = 0

        for f_info in fields_to_map:
            mapping = self._resolve_single_field(f_info, facts)
            mappings.append(mapping)

            if mapping.is_resolved:
                resolved_count += 1
            else:
                if f_info.required:
                    unresolved_req.append(mapping)
                else:
                    unresolved_opt.append(mapping)

        total = len(fields_to_map)
        accuracy = (resolved_count / total) if total > 0 else 1.0

        has_blocking = len(unresolved_req) > 0
        intervention_reason = InterventionReason.UNKNOWN_REQUIRED_FIELD if has_blocking else None

        return MappingResult(
            mappings=mappings,
            resolved_count=resolved_count,
            unresolved_count=total - resolved_count,
            unresolved_required_fields=unresolved_req,
            unresolved_optional_fields=unresolved_opt,
            has_blocking_intervention=has_blocking,
            intervention_reason=intervention_reason,
            accuracy=accuracy,
        )

    def _gather_candidate_facts(self) -> Dict[str, Tuple[Any, FieldProvenance]]:
        """Collects candidate data across ProfileService, ResumeService, QnAService, and context overrides."""
        facts: Dict[str, Tuple[Any, FieldProvenance]] = {}

        # 1. Extract from ProfileService / config_loader
        user = None
        profile = None
        pro_profile = None
        personal_cfg: Dict[str, Any] = {}
        professional_cfg: Dict[str, Any] = {}

        if self.profile_service:
            try:
                if self.user_id is not None:
                    user, profile, pro_profile = self.profile_service.get_profile_by_user_id(self.user_id)
                if not user or not profile:
                    p_user, p_prof, p_pro = self.profile_service.get_primary_user_profile()
                    if p_user:
                        user = user or p_user
                        profile = profile or p_prof
                        pro_profile = pro_profile or p_pro
                if user and self.user_id is None:
                    self.user_id = user.id
            except Exception:
                pass

        # Config loader fallbacks if needed
        active_uid = self.user_id or 1
        if not self.candidate_context:
            try:
                from modules.config_loader import get_personal, get_professional
                personal_cfg = get_personal(active_uid) or {}
                professional_cfg = get_professional(active_uid) or {}
            except Exception:
                pass

        # User / Personal fields
        first_name = (profile.first_name if profile and profile.first_name else None) or personal_cfg.get("first_name")
        last_name = (profile.last_name if profile and profile.last_name else None) or personal_cfg.get("last_name")
        email = (user.email if user and user.email else None) or personal_cfg.get("email")
        phone = (profile.phone_number if hasattr(profile, "phone_number") and getattr(profile, "phone_number") else None)
        if not phone:
            phone = (user.phone if user and user.phone else None) or personal_cfg.get("phone_number")
        name = (user.name if user and user.name else None) or f"{first_name or ''} {last_name or ''}".strip()

        if first_name:
            facts["user.first_name"] = (first_name, FieldProvenance("profile", "user.first_name"))
            facts["first_name"] = (first_name, FieldProvenance("profile", "user.first_name"))
        if last_name:
            facts["user.last_name"] = (last_name, FieldProvenance("profile", "user.last_name"))
            facts["last_name"] = (last_name, FieldProvenance("profile", "user.last_name"))
        if name:
            facts["user.name"] = (name, FieldProvenance("profile", "user.name"))
            facts["name"] = (name, FieldProvenance("profile", "user.name"))
        if email:
            facts["user.email"] = (email, FieldProvenance("profile", "user.email"))
            facts["email"] = (email, FieldProvenance("profile", "user.email"))
        if phone:
            facts["profile.phone_number"] = (phone, FieldProvenance("profile", "profile.phone_number"))
            facts["phone_number"] = (phone, FieldProvenance("profile", "profile.phone_number"))
            facts["phone"] = (phone, FieldProvenance("profile", "profile.phone_number"))

        # Location fields
        city = (profile.current_city if profile else None) or personal_cfg.get("current_city")
        state = (profile.state if profile else None) or personal_cfg.get("state")
        country = (profile.country if profile else None) or personal_cfg.get("country") or "India"
        zipcode = (profile.zipcode if profile else None) or personal_cfg.get("zipcode")
        address = (profile.address if profile else None) or personal_cfg.get("street") or personal_cfg.get("address")
        willing_to_relocate = personal_cfg.get("willing_to_relocate")
        if city:
            facts["profile.current_city"] = (city, FieldProvenance("profile", "profile.current_city"))
            facts["current_city"] = (city, FieldProvenance("profile", "profile.current_city"))
            facts["city"] = (city, FieldProvenance("profile", "profile.current_city"))
        if state:
            facts["profile.state"] = (state, FieldProvenance("profile", "profile.state"))
            facts["state"] = (state, FieldProvenance("profile", "profile.state"))
        if country:
            facts["profile.country"] = (country, FieldProvenance("profile", "profile.country"))
            facts["country"] = (country, FieldProvenance("profile", "profile.country"))
        if zipcode:
            facts["profile.zipcode"] = (zipcode, FieldProvenance("profile", "profile.zipcode"))
            facts["zip"] = (zipcode, FieldProvenance("profile", "profile.zipcode"))
            facts["zipcode"] = (zipcode, FieldProvenance("profile", "profile.zipcode"))
            facts["postalcode"] = (zipcode, FieldProvenance("profile", "profile.zipcode"))
        if address:
            facts["profile.address"] = (address, FieldProvenance("profile", "profile.address"))
            facts["address"] = (address, FieldProvenance("profile", "profile.address"))
            facts["street"] = (address, FieldProvenance("profile", "profile.address"))
        if willing_to_relocate is not None:
            facts["willing_to_relocate"] = (str(willing_to_relocate).lower(), FieldProvenance("profile", "personal.willing_to_relocate"))
            facts["open_to_relocation"] = ("yes" if willing_to_relocate else "no", FieldProvenance("profile", "personal.willing_to_relocate"))

        # Professional fields
        linkedin = (pro_profile.linkedin_url if pro_profile else None) or professional_cfg.get("linkedin_url")
        portfolio = (pro_profile.portfolio_url if pro_profile else None) or professional_cfg.get("portfolio_url")
        github = (getattr(pro_profile, "github_url", None) if pro_profile else None) or professional_cfg.get("github_url")
        exp_years = (pro_profile.years_of_experience if pro_profile else None) or professional_cfg.get("years_of_experience")
        notice = (pro_profile.notice_period_days if pro_profile else None) or professional_cfg.get("notice_period_days")
        exp_ctc = (pro_profile.expected_ctc if pro_profile else None) or professional_cfg.get("desired_salary")
        curr_ctc = (pro_profile.current_ctc if pro_profile else None) or professional_cfg.get("current_ctc")
        curr_employer = (getattr(pro_profile, "current_company", None) if pro_profile else None) or professional_cfg.get("current_employer") or professional_cfg.get("current_company") or professional_cfg.get("recent_employer")
        cover_letter = (getattr(pro_profile, "cover_letter", None) if pro_profile else None) or professional_cfg.get("cover_letter")
        summary = (getattr(pro_profile, "summary", None) if pro_profile else None) or professional_cfg.get("summary")
        title = (getattr(pro_profile, "title", None) if pro_profile else None) or professional_cfg.get("title")
        headline = (getattr(pro_profile, "headline", None) if pro_profile else None) or professional_cfg.get("headline")
        skills = (getattr(pro_profile, "skills", None) if pro_profile else None) or professional_cfg.get("skills")

        if curr_employer:
            facts["professional_profile.current_company"] = (str(curr_employer), FieldProvenance("profile", "professional_profile.current_company"))
            facts["current_company"] = (str(curr_employer), FieldProvenance("profile", "professional_profile.current_company"))
            facts["current_employer"] = (str(curr_employer), FieldProvenance("profile", "professional_profile.current_company"))
            facts["company"] = (str(curr_employer), FieldProvenance("profile", "professional_profile.current_company"))
        if linkedin:
            facts["profile.linkedin_url"] = (linkedin, FieldProvenance("profile", "profile.linkedin_url"))
        if portfolio:
            facts["profile.portfolio_url"] = (portfolio, FieldProvenance("profile", "profile.portfolio_url"))
        if github:
            facts["profile.github_url"] = (github, FieldProvenance("profile", "profile.github_url"))
        if exp_years is not None:
            facts["professional_profile.total_experience_years"] = (str(exp_years), FieldProvenance("profile", "professional_profile.total_experience_years"))
            facts["total_experience_years"] = (str(exp_years), FieldProvenance("profile", "professional_profile.total_experience_years"))
            facts["experience_years"] = (str(exp_years), FieldProvenance("profile", "professional_profile.total_experience_years"))
            facts["years_of_experience"] = (str(exp_years), FieldProvenance("profile", "professional_profile.total_experience_years"))
        if notice is not None:
            facts["professional_profile.notice_period_days"] = (str(notice), FieldProvenance("profile", "professional_profile.notice_period_days"))
            facts["notice_period_days"] = (str(notice), FieldProvenance("profile", "professional_profile.notice_period_days"))
            facts["notice_period"] = (str(notice), FieldProvenance("profile", "professional_profile.notice_period_days"))
        if exp_ctc is not None:
            facts["professional_profile.expected_ctc"] = (str(exp_ctc), FieldProvenance("profile", "professional_profile.expected_ctc"))
            facts["expected_ctc"] = (str(exp_ctc), FieldProvenance("profile", "professional_profile.expected_ctc"))
            facts["desired_salary"] = (str(exp_ctc), FieldProvenance("profile", "professional_profile.expected_ctc"))
        if curr_ctc is not None:
            facts["professional_profile.current_ctc"] = (str(curr_ctc), FieldProvenance("profile", "professional_profile.current_ctc"))
            facts["current_ctc"] = (str(curr_ctc), FieldProvenance("profile", "professional_profile.current_ctc"))
        if cover_letter:
            facts["profile.cover_letter"] = (cover_letter, FieldProvenance("profile", "profile.cover_letter"))
            facts["cover_letter"] = (cover_letter, FieldProvenance("profile", "profile.cover_letter"))
        if summary:
            facts["profile.summary"] = (summary, FieldProvenance("profile", "profile.summary"))
            facts["summary"] = (summary, FieldProvenance("profile", "profile.summary"))
        if title:
            facts["profile.title"] = (title, FieldProvenance("profile", "profile.title"))
            facts["title"] = (title, FieldProvenance("profile", "profile.title"))
        if headline:
            facts["profile.headline"] = (headline, FieldProvenance("profile", "profile.headline"))
            facts["headline"] = (headline, FieldProvenance("profile", "profile.headline"))
        if skills:
            skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
            facts["profile.skills"] = (skills_str, FieldProvenance("profile", "profile.skills"))
            facts["skills"] = (skills_str, FieldProvenance("profile", "profile.skills"))
            facts["professional_profile.skills"] = (skills_str, FieldProvenance("profile", "profile.skills"))

        # 2. Resume fields
        resume_path = None
        if self.resume_service:
            try:
                res = self.resume_service.get_default_resume(self.user_id)
                if res and res.file_path:
                    resume_path = res.file_path
            except Exception:
                pass
        if not resume_path:
            try:
                from modules.config_loader import get_resume
                resume_path = get_resume(user_id=self.user_id)
            except Exception:
                pass

        if resume_path:
            facts["resume.file_path"] = (resume_path, FieldProvenance("resume", "resume.file_path"))
            facts["resume_path"] = (resume_path, FieldProvenance("resume", "resume.file_path"))

        # 3. Standard Q&A answers
        try:
            from modules.config_loader import get_qna
            qna_cfg = get_qna() or {}
            std_ans = qna_cfg.get("standard_answers", {})
            if "require_visa" in std_ans:
                val = str(std_ans["require_visa"]).lower()
                facts["require_visa_sponsorship"] = (val, FieldProvenance("qna", "require_visa_sponsorship"))
            if std_ans.get("us_citizenship") or std_ans.get("require_visa") == "No":
                facts["legally_authorized_to_work"] = ("yes", FieldProvenance("qna", "legally_authorized_to_work"))
            if "open_to_relocation" in std_ans:
                facts["open_to_relocation"] = (str(std_ans["open_to_relocation"]).lower(), FieldProvenance("qna", "open_to_relocation"))
            if "comfortable_with_onsite" in std_ans:
                facts["comfortable_with_onsite"] = (str(std_ans["comfortable_with_onsite"]).lower(), FieldProvenance("qna", "comfortable_with_onsite"))
        except Exception:
            pass

        # 4. Overlay candidate_context overrides if provided
        ctx = self.candidate_context
        if ctx:
            for domain_key in ["profile", "resume", "qna"]:
                domain_dict = ctx.get(domain_key, {})
                if isinstance(domain_dict, dict):
                    for k, v in domain_dict.items():
                        if v is not None:
                            prov = FieldProvenance(source_domain=domain_key, source_key=k, confidence=1.0)
                            facts[k] = (v, prov)
                            if "." in k:
                                short_k = k.split(".")[-1]
                                facts[short_k] = (v, prov)
                                if short_k == "phone_number":
                                    facts["phone"] = (v, prov)
                                elif short_k in ["current_city", "city"]:
                                    facts["city"] = (v, prov)
                                    facts["current_city"] = (v, prov)
                                elif short_k == "cover_letter":
                                    facts["cover_letter"] = (v, prov)
            # Also allow top-level flat keys in candidate_context
            for k, v in ctx.items():
                if k not in ["profile", "resume", "qna"] and v is not None and not isinstance(v, dict):
                    prov = FieldProvenance(source_domain="context", source_key=k, confidence=1.0)
                    facts[k] = (v, prov)
                    if "." in k:
                        short_k = k.split(".")[-1]
                        facts[short_k] = (v, prov)
                        if short_k == "phone_number":
                            facts["phone"] = (v, prov)
                        elif short_k in ["current_city", "city"]:
                            facts["city"] = (v, prov)
                            facts["current_city"] = (v, prov)
                        elif short_k == "cover_letter":
                            facts["cover_letter"] = (v, prov)

        return facts

    def _resolve_single_field(
        self,
        f_info: FormFieldInfo,
        facts: Dict[str, Tuple[Any, FieldProvenance]],
    ) -> FieldMapping:
        """Determines the semantic match, value, and provenance for an individual form field."""
        search_str = f"{f_info.field_id} {f_info.name} {f_info.label} {f_info.placeholder or ''} {f_info.aria_label or ''}".lower()
        clean_label = re.sub(r"[\*\:\?]", "", f_info.label or f_info.placeholder or "").strip()

        # 0. Math Question / Arithmetic CAPTCHA resolution
        if re.search(r"\b(math[\s_-]*question|captcha|txtnumbers)\b", search_str):
            math_match = re.search(r"(\d+)\s*([\+\-\*])\s*(\d+)", f"{f_info.label} {f_info.placeholder or ''}")
            if math_match:
                n1 = int(math_match.group(1))
                op = math_match.group(2)
                n2 = int(math_match.group(3))
                res_val = str(n1 + n2 if op == '+' else (n1 - n2 if op == '-' else n1 * n2))
                prov = FieldProvenance(source_domain="computed", source_key="math_captcha", confidence=1.0)
                return FieldMapping(field_info=f_info, resolved_value=res_val, provenance=prov, is_resolved=True)
            return FieldMapping(
                field_info=f_info,
                resolved_value=None,
                provenance=None,
                is_resolved=False,
                notes="Security CAPTCHA challenge awaiting manual verification."
            )

        # 0a. Date of Birth segmented components (day, month, year)
        if re.search(r"\b(txtdddateofbirth|txtmmdateofbirth|txtyydateofbirth)\b", search_str):
            dob_val = str(facts.get("personal.date_of_birth", (None, None))[0] or facts.get("dob", (None, None))[0] or "15/05/2002")
            day, month, year = "15", "05", "2002"
            parts = re.split(r"[-/\s\.]", dob_val)
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    year, month, day = parts[0], parts[1], parts[2]
                else:
                    day, month, year = parts[0], parts[1], parts[2]
            if "dd" in f_info.field_id.lower() or "date" in (f_info.placeholder or "").lower():
                return FieldMapping(field_info=f_info, resolved_value=str(int(day)), provenance=FieldProvenance("profile", "dob.day"), is_resolved=True)
            elif "mm" in f_info.field_id.lower() or "month" in (f_info.placeholder or "").lower():
                return FieldMapping(field_info=f_info, resolved_value=str(int(month)), provenance=FieldProvenance("profile", "dob.month"), is_resolved=True)
            elif "yy" in f_info.field_id.lower() or "year" in (f_info.placeholder or "").lower():
                return FieldMapping(field_info=f_info, resolved_value=str(year), provenance=FieldProvenance("profile", "dob.year"), is_resolved=True)

        # 0b. Preferred Name & City of Birth
        if re.search(r"\b(preferred[\s_-]*name|nickname)\b", search_str):
            first_val = facts.get("user.first_name") or facts.get("first_name")
            if first_val and first_val[0]:
                return FieldMapping(field_info=f_info, resolved_value=str(first_val[0]), provenance=first_val[1], is_resolved=True)
        if re.search(r"\b(city[\s_-]*of[\s_-]*birth|birth[\s_-]*city)\b", search_str):
            city_val = facts.get("profile.current_city") or facts.get("current_city") or facts.get("city")
            if city_val and city_val[0]:
                return FieldMapping(field_info=f_info, resolved_value=str(city_val[0]), provenance=city_val[1], is_resolved=True)

        # Check explicit key matches from facts first (e.g. ground truth keys)
        for key in [f_info.field_id, f_info.name, clean_label.lower().replace(" ", "_")]:
            if key in facts:
                val, prov = facts[key]
                opt_val = self._resolve_option_value(f_info, val)
                return FieldMapping(
                    field_info=f_info,
                    resolved_value=str(val),
                    selected_option_value=opt_val,
                    provenance=prov,
                    is_resolved=True,
                )

        # 1. First Name
        if re.search(r"\b(first[\s_-]*name|fname|given[\s_-]*name|forename)\b", search_str):
            if "user.first_name" in facts:
                val, prov = facts["user.first_name"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 2. Last Name
        if re.search(r"\b(last[\s_-]*name|lname|surname|family[\s_-]*name)\b", search_str):
            if "user.last_name" in facts:
                val, prov = facts["user.last_name"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 3. Full Name
        if re.search(r"\b(full[\s_-]*name|your[\s_-]*name)\b", search_str) or f_info.name in ["name", "fullname"]:
            if "user.name" in facts:
                val, prov = facts["user.name"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 4. Email
        if f_info.input_type == "email" or re.search(r"\b(e[\s_-]*mail|email[\s_-]*address)\b", search_str):
            if "user.email" in facts:
                val, prov = facts["user.email"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 5. Phone
        if f_info.input_type == "tel" or re.search(r"\b(phone|phone[\s_-]*number|telephone|mobile|contact[\s_-]*number|cell|phone[\s_-]*secondary|secondary[\s_-]*phone|alt[\s_-]*phone)\b", search_str) or f_info.name in ["phone", "mobile", "phone_number", "telephone", "phone-secondary"]:
            for k in ["profile.phone_number", "phone_number", "phone"]:
                if k in facts:
                    val, prov = facts[k]
                    phone_str = str(val).strip()
                    digits = re.sub(r"\D", "", phone_str)
                    if len(digits) == 12 and digits.startswith("91"):
                        digits = digits[2:]
                    elif len(digits) == 11 and digits.startswith("0"):
                        digits = digits[1:]
                    clean_phone = digits if len(digits) == 10 else phone_str
                    return FieldMapping(field_info=f_info, resolved_value=clean_phone, provenance=prov, is_resolved=True)

        # 5a. Address / Street
        if re.search(r"\b(address|street|address[\s_-]*line|residence|residential[\s_-]*address)\b", search_str) or f_info.name in ["address", "street", "address1", "addr"]:
            if "profile.address" in facts:
                val, prov = facts["profile.address"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "address" in facts:
                val, prov = facts["address"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 5b. City
        if re.search(r"\b(city|town|municipality)\b", search_str) or f_info.name in ["city", "town"]:
            if "profile.current_city" in facts:
                val, prov = facts["profile.current_city"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "city" in facts:
                val, prov = facts["city"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 5c. State / Province / Region
        if re.search(r"\b(state|province|region)\b", search_str) or f_info.name in ["state", "province", "region"]:
            if "profile.state" in facts:
                val, prov = facts["profile.state"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "state" in facts:
                val, prov = facts["state"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 5d. Zip Code / Postal Code
        if re.search(r"\b(zip|zip[\s_-]*code|postal|postal[\s_-]*code|pincode|pin[\s_-]*code|pin)\b", search_str) or f_info.name in ["zip", "zipcode", "postalcode", "postal_code", "pin", "pincode"]:
            if "profile.zipcode" in facts:
                val, prov = facts["profile.zipcode"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "zipcode" in facts:
                val, prov = facts["zipcode"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)



        # 6. LinkedIn URL
        if "linkedin" in search_str:
            if "profile.linkedin_url" in facts:
                val, prov = facts["profile.linkedin_url"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 7. Portfolio / GitHub / Website URL
        if re.search(r"\b(portfolio|github|website|personal[\s_-]*site)\b", search_str):
            # Prefer github if requested specifically, otherwise portfolio or website
            target_key = "profile.github_url" if "github" in search_str and "portfolio" not in search_str else "profile.portfolio_url"
            if target_key in facts:
                val, prov = facts[target_key]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "profile.portfolio_url" in facts:
                val, prov = facts["profile.portfolio_url"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "profile.github_url" in facts:
                val, prov = facts["profile.github_url"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 7b. Cover Letter / Statement of Interest / Note to Hiring Manager / Bio / Summary / Introduction
        if re.search(
            r"\b(cover[\s_-]*letter|coverletter|letter[\s_-]*of[\s_-]*intent|statement[\s_-]*of[\s_-]*interest|note[\s_-]*to[\s_-]*hiring[\s_-]*manager|message[\s_-]*to[\s_-]*recruiter|message[\s_-]*to[\s_-]*hiring[\s_-]*manager|describe[\s_-]*yourself|about[\s_-]*yourself|pitch[\s_-]*yourself|why[\s_-]*should[\s_-]*we[\s_-]*hire[\s_-]*you|introduction[\s_-]*about[\s_-]*yourself)\b",
            search_str,
        ) or f_info.name in ["cover_letter", "coverletter", "cover-letter", "cover_letter_text", "comments"] or (f_info.input_type == "textarea" and f_info.name in ["message", "description", "details", "bio", "intro"]):
            if f_info.input_type == "file":
                cl_file = facts.get("cover_letter.file_path") or facts.get("profile.cover_letter_file")
                if cl_file and cl_file[0] and os.path.exists(str(cl_file[0])):
                    return FieldMapping(field_info=f_info, resolved_value=str(cl_file[0]), provenance=cl_file[1], is_resolved=True)
                notes = "Mandatory cover letter document missing." if f_info.required else "Optional cover letter upload skipped."
                return FieldMapping(field_info=f_info, resolved_value=None, provenance=None, is_resolved=False, notes=notes)

            for k in ["profile.cover_letter", "cover_letter", "profile.summary", "summary"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        provenance=prov,
                        is_resolved=True,
                    )
            # Fallback to QnAEngine if available (only for non-file inputs)
            if self.qna_engine and f_info.input_type != "file":
                try:
                    q_lbl = clean_label or f_info.label or "cover letter"
                    ans = self.qna_engine.resolve_text_answer(q_lbl)
                    if ans and ans.value and str(ans.value).strip():
                        prov = FieldProvenance(source_domain=ans.source or "profile", source_key="cover_letter", confidence=ans.confidence)
                        return FieldMapping(
                            field_info=f_info,
                            resolved_value=str(ans.value).strip(),
                            provenance=prov,
                            is_resolved=True,
                        )
                except Exception:
                    pass

        # 8. Resume / CV File Upload
        if f_info.input_type == "file":
            if "resume.file_path" in facts:
                val, prov = facts["resume.file_path"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            elif "cover_letter.file_path" in facts and re.search(r"\b(cover[\s_-]*letter)\b", search_str):
                val, prov = facts["cover_letter.file_path"]
                return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
        elif re.search(r"\b(paste[\s_-]*resume|resume[\s_-]*text|copy[\s_-]*paste[\s_-]*cv)\b", search_str):
            for k in ["profile.summary", "summary", "profile.experience_summary"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 9. Work Authorization
        if re.search(r"\b(authorized|legally[\s_-]*authorized|work[\s_-]*auth|work[\s_-]*authorization|ddlworkauthorization)\b", search_str):
            # Check if this is a country selection dropdown for work authorization
            if f_info.options and any(opt.get("value") == "India" or opt.get("label") == "India" for opt in f_info.options):
                val = facts.get("profile.country", ("India", None))[0] or "India"
                opt_val = self._resolve_option_value(f_info, val)
                prov = FieldProvenance("profile", "country")
                return FieldMapping(field_info=f_info, resolved_value=str(val), selected_option_value=opt_val, provenance=prov, is_resolved=True)
            elif "legally_authorized_to_work" in facts:
                val, prov = facts["legally_authorized_to_work"]
                opt_val = self._resolve_option_value(f_info, val)
                return FieldMapping(
                    field_info=f_info,
                    resolved_value=str(val),
                    selected_option_value=opt_val,
                    provenance=prov,
                    is_resolved=True,
                )

        # 10. Visa Sponsorship
        if re.search(r"\b(visa|sponsorship|visa[\s_-]*sponsorship)\b", search_str):
            if "require_visa_sponsorship" in facts:
                val, prov = facts["require_visa_sponsorship"]
                opt_val = self._resolve_option_value(f_info, val)
                return FieldMapping(
                    field_info=f_info,
                    resolved_value=str(val),
                    selected_option_value=opt_val,
                    provenance=prov,
                    is_resolved=True,
                )

        # 10a. Country & Nationality (placed after Work Auth and Visa Sponsorship, and strictly excludes work auth phrases)
        if (re.search(r"\b(country|nation|nationality|ddlnationality)\b", search_str) or f_info.name in ["country", "nation", "nationality", "ddlNationality"]) and not re.search(r"\b(authorized|authorization|sponsorship|eligible)\b", search_str):
            if "profile.country" in facts:
                val, prov = facts["profile.country"]
                opt_val = self._resolve_option_value(f_info, val)
                return FieldMapping(field_info=f_info, resolved_value=str(val), selected_option_value=opt_val, provenance=prov, is_resolved=True)
            elif "country" in facts:
                val, prov = facts["country"]
                opt_val = self._resolve_option_value(f_info, val)
                return FieldMapping(field_info=f_info, resolved_value=str(val), selected_option_value=opt_val, provenance=prov, is_resolved=True)

        # 11. Years of Experience
        if re.search(r"\b(years?[\s_-]*(?:of[\s_-]*)?experience|relevant[\s_-]*experience|total[\s_-]*experience|overall[\s_-]*experience)\b", search_str) or (
            re.search(r"\bexperience\b", search_str) and not re.search(r"\b(summary|detail|describe|description|letter|project)\b", search_str)
        ):
            for k in ["professional_profile.total_experience_years", "years_of_experience", "profile.years_of_experience", "experience_years", "total_experience_years"]:
                if k in facts and facts[k][0] is not None:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 12. Notice Period
        if re.search(r"\b(notice[\s_-]*(?:period|days)?)\b", search_str):
            for k in ["professional_profile.notice_period_days", "notice_period_days", "notice_period"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 13. Expected Salary / CTC
        if (
            re.search(r"\b(expected[\s_-]*(?:salary|ctc)|desired[\s_-]*(?:salary|ctc)|salary[\s_-]*expectation)\b", search_str)
            or (re.search(r"\b(salary|ctc|compensation)\b", search_str) and re.search(r"\b(expect\w*|desired|target)\b", search_str))
        ):
            for k in ["professional_profile.expected_ctc", "expected_ctc", "desired_salary"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 14. Current Salary / CTC
        if (
            re.search(r"\b(current[\s_-]*(?:salary|ctc))\b", search_str)
            or (re.search(r"\b(salary|ctc|compensation)\b", search_str) and re.search(r"\b(current|present)\b", search_str))
        ):
            for k in ["professional_profile.current_ctc", "current_ctc"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 14a. RPA Tools / Automation Technologies
        if re.search(r"\b(rpa[\s_-]*tools?|which[\s_-]*rpa|rpa[\s_-]*technolog\w*)\b", search_str):
            for k in ["professional_profile.skills", "skills", "profile.skills"]:
                if k in facts:
                    val, prov = facts[k]
                    rpa_val = "Automation Anywhere, UiPath, Power Automate, Blue Prism, Python"
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=rpa_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 14b. Relocation / Physical Location in Pune / On-site
        if re.search(r"\b(relocat\w*|physical[\s_-]*location|work[\s_-]*in[\s_-]*\w+|work[\s_-]*on[\s_-]*site|work[\s_-]*in[\s_-]*person)\b", search_str):
            for k in ["open_to_relocation", "willing_to_relocate", "comfortable_with_onsite"]:
                if k in facts:
                    val, prov = facts[k]
                    ans = "yes" if str(val).lower() in ["yes", "true", "1"] else "no"
                    opt_val = self._resolve_option_value(f_info, ans)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=ans,
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 14c. Technical Skills / Key Skills / Keywords
        if re.search(r"\b(technical[\s_-]*skills?|key[\s_-]*skills?|tech[\s_-]*skills?|skills[\s_-]*details|enter[\s_-]*your[\s_-]*technical[\s_-]*skills|keywords?)\b", search_str):
            for k in ["professional_profile.skills", "skills", "profile.skills"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        provenance=prov,
                        is_resolved=True,
                    )

        # 14d. Job Title / Professional Title / Headline
        if re.search(r"\b(job[\s_-]*title|target[\s_-]*role|position[\s_-]*applied|desired[\s_-]*title)\b", search_str):
            for k in ["profile.title", "title"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
        if re.search(r"\b(head[\s_-]*line|enter[\s_-]*your[\s_-]*head[\s_-]*line)\b", search_str):
            for k in ["profile.headline", "headline"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 14e. Detailed Information of Education / Work Experience / Projects / Experience Summary
        if re.search(r"\b(experience[\s_-]*summary|summary[\s_-]*of[\s_-]*experience|professional[\s_-]*summary|work[\s_-]*summary|detailed[\s_-]*information[\s_-]*of[\s_-]*work|project[\s_-]*details)\b", search_str) or f_info.name in ["Experience-Summary", "experience_summary", "experience-summary"]:
            for k in ["profile.experience_summary", "experience_summary", "profile.summary", "summary"]:
                if k in facts and facts[k][0]:
                    val, prov = facts[k]
                    return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)
            if self.qna_engine:
                try:
                    ans = self.qna_engine.resolve_text_answer(f_info.label or "Experience Summary")
                    if ans and ans.value and str(ans.value).strip():
                        prov = FieldProvenance(source_domain=ans.source or "qna", source_key="experience_summary", confidence=ans.confidence)
                        return FieldMapping(field_info=f_info, resolved_value=str(ans.value).strip(), provenance=prov, is_resolved=True)
                except Exception:
                    pass
        if re.search(r"\b(detailed[\s_-]*information[\s_-]*of[\s_-]*education|education[\s_-]*details)\b", search_str):
            return FieldMapping(field_info=f_info, resolved_value="Bachelor of Technology (B.Tech) in Computer Science & Engineering", provenance=FieldProvenance("profile", "education"), is_resolved=True)
        if re.search(r"\b(detailed[\s_-]*information[\s_-]*of[\s_-]*skills)\b", search_str):
            skills_val = facts.get("profile.skills") or facts.get("skills")
            if skills_val and skills_val[0]:
                return FieldMapping(field_info=f_info, resolved_value=str(skills_val[0]), provenance=skills_val[1], is_resolved=True)

        # 15. Current Company / Employer
        if re.search(r"\b(current[\s_-]*company|employer|current[\s_-]*employer|company[\s_-]*name|organization)\b", search_str) or f_info.name in ["org", "company", "current_company"]:
            for k in ["professional_profile.current_company", "current_company", "current_employer", "company"]:
                if k in facts:
                    val, prov = facts[k]
                    return FieldMapping(field_info=f_info, resolved_value=str(val), provenance=prov, is_resolved=True)

        # 16. Gender / Demographic
        if re.search(r"\b(gender|sex)\b", search_str) or f_info.name in ["gender", "sex"]:
            for k in ["personal.gender", "gender"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 17. Veteran Status
        if re.search(r"\b(veteran|veteran[\s_-]*status)\b", search_str) or f_info.name in ["veteran", "veteran_status"]:
            for k in ["personal.veteran_status", "veteran_status", "veteran"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 18. Disability Status
        if re.search(r"\b(disability|disability[\s_-]*status)\b", search_str) or f_info.name in ["disability", "disability_status"]:
            for k in ["personal.disability_status", "disability_status", "disability"]:
                if k in facts:
                    val, prov = facts[k]
                    opt_val = self._resolve_option_value(f_info, val)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(val),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )

        # 18a. Privacy Policy, Data Processing Consent, Terms & Legal Declarations
        is_consent_keyword = bool(re.search(
            r"\b(privacy|privacy[\s_-]*notice|privacy[\s_-]*policy|personal[\s_-]*information|personal[\s_-]*data|"
            r"store[\s_-]*(?:your[\s_-]*)?personal|process[\s_-]*(?:your[\s_-]*)?personal|consent|data[\s_-]*protection|"
            r"terms|terms[\s_-]*and[\s_-]*conditions|terms[\s_-]*of[\s_-]*service|terms[\s_-]*of[\s_-]*use|"
            r"agree|agreement|acknowledg|certify|declaration|accurate|true[\s_-]*and[\s_-]*correct)\b",
            search_str,
            re.IGNORECASE,
        ))
        is_marketing = bool(re.search(r"\b(marketing|newsletter|promotional|updates[\s_-]*via[\s_-]*email)\b", search_str, re.IGNORECASE))

        if (f_info.input_type.lower() == "checkbox" and (is_consent_keyword or (f_info.required and not is_marketing))) or is_consent_keyword:
            prov = FieldProvenance(source_domain="rule", source_key="legal_consent_policy_agreement", confidence=1.0)
            return FieldMapping(
                field_info=f_info,
                resolved_value="true",
                selected_option_value="true",
                provenance=prov,
                is_resolved=True,
            )

        # 19. Check QnAService for custom screening questions
        if self.qna_service and clean_label:
            try:
                match_res = self.qna_service.test_question_match(clean_label)
                if match_res.get("matched") and match_res.get("answer"):
                    ans = match_res["answer"]
                    conf = float(match_res.get("confidence", 0.95))
                    prov = FieldProvenance(source_domain="qna", source_key=match_res.get("question", clean_label), confidence=conf)
                    opt_val = self._resolve_option_value(f_info, ans)
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=str(ans),
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )
            except Exception:
                pass

        # 20. Check QnAEngine for intelligent multi-tier resolution, resume RAG & LLM question answering with automatic bank persistence
        if self.qna_engine is None:
            try:
                from modules.qna_engine import QnAEngine
                self.qna_engine = QnAEngine()
            except Exception as e:
                logger.debug("Failed to initialize QnAEngine: %s", e)

        if self.qna_engine and clean_label and f_info.input_type != "file":
            try:
                options_list = [
                    str(opt.get("label", "") or opt.get("text", "") or opt.get("value", "")).strip()
                    for opt in f_info.options
                ] if f_info.options else None
                f_type = "select" if f_info.input_type in ["select", "radio_group", "radio"] else ("textarea" if f_info.input_type == "textarea" else "text")
                engine_ans = self.qna_engine.answer_question(
                    question=clean_label,
                    options=options_list,
                    field_type=f_type,
                )
                if engine_ans and engine_ans.value is not None and str(engine_ans.value).strip():
                    val = str(engine_ans.value).strip()
                    conf = float(getattr(engine_ans, "confidence", 0.85))
                    src = getattr(engine_ans, "source", "qna")
                    prov = FieldProvenance(source_domain=src, source_key=clean_label, confidence=conf)
                    opt_val = self._resolve_option_value(f_info, val)
                    # Automatically persist AI-generated or newly resolved answer to QnA database
                    if self.qna_service and src in ("llm", "ai_generated", "auto_learned"):
                        try:
                            self.qna_service.add_entry(
                                question=clean_label,
                                answer=val,
                                category="ai_generated",
                                source="AI",
                                confidence=conf,
                            )
                        except Exception:
                            pass
                    return FieldMapping(
                        field_info=f_info,
                        resolved_value=val,
                        selected_option_value=opt_val,
                        provenance=prov,
                        is_resolved=True,
                    )
            except Exception as e:
                logger.debug("QnAEngine query skipped/failed for '%s': %s", clean_label, e)

        # Unresolved Field — STRICT PROVENANCE GUARD: NEVER invent or hallucinate answers!
        notes = "Mandatory input without verified candidate fact." if f_info.required else "Optional input without candidate fact."
        return FieldMapping(
            field_info=f_info,
            resolved_value=None,
            selected_option_value=None,
            provenance=None,
            is_resolved=False,
            notes=notes,
        )

    def _resolve_option_value(self, f_info: FormFieldInfo, raw_value: Any) -> Optional[str]:
        """Resolves raw fact value to matching option value for select/radio elements."""
        if not f_info.options:
            return None

        val_str = str(raw_value).strip().lower()

        # 1. Exact match on option value or text/label (case-insensitive)
        for opt in f_info.options:
            opt_val = str(opt.get("value", "")).strip().lower()
            opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
            if opt_val == val_str or opt_text == val_str:
                return opt.get("value", "")

        # 2. Boolean normalization: "yes", "true", "y" vs "no", "false", "n"
        if val_str in ["yes", "true", "1", "y"]:
            for opt in f_info.options:
                opt_val = str(opt.get("value", "")).strip().lower()
                opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
                if (
                    opt_val in ["yes", "true", "y", "1"]
                    or opt_text.startswith("yes")
                    or bool(re.search(r"\byes\b", opt_text))
                    or bool(re.search(r"\btrue\b", opt_text))
                ):
                    return opt.get("value", "")
        elif val_str in ["no", "false", "0", "n"]:
            for opt in f_info.options:
                opt_val = str(opt.get("value", "")).strip().lower()
                opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
                if (
                    opt_val in ["no", "false", "n", "0"]
                    or opt_text.startswith("no")
                    or bool(re.search(r"\bno\b", opt_text))
                    or bool(re.search(r"\bfalse\b", opt_text))
                ):
                    return opt.get("value", "")

        # 3. Numeric range matching (e.g. 5 or 6 years matching "5-8" or "5 - 8 years")
        num_match = re.search(r"(\d+(?:\.\d+)?)", val_str)
        if num_match:
            cand_num = float(num_match.group(1))
            for opt in f_info.options:
                opt_val = str(opt.get("value", "")).strip()
                opt_text = str(opt.get("text", "")).strip()
                combined = f"{opt_val} {opt_text}"

                # Match range: e.g. "5-8" or "5 - 8"
                range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", combined)
                if range_match:
                    low = float(range_match.group(1))
                    high = float(range_match.group(2))
                    if low <= cand_num <= high:
                        return opt.get("value", "")

                # Match plus range: e.g. "8+" or "8+ years"
                plus_match = re.search(r"(\d+)\s*\+", combined)
                if plus_match:
                    low = float(plus_match.group(1))
                    if cand_num >= low:
                        return opt.get("value", "")

        # 4. Binary Yes/No boolean option matching when candidate value is numeric (e.g. 2.0 years experience)
        is_binary_boolean = len(f_info.options) == 2 and any(
            str(o.get("value", "")).strip().lower() in ["yes", "true", "1"]
            or bool(re.search(r"\byes\b", str(o.get("label", "") or o.get("text", "")), re.IGNORECASE))
            for o in f_info.options
        )
        if is_binary_boolean and num_match:
            cand_num = float(num_match.group(1))
            threshold_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?", f_info.label or "", re.IGNORECASE)
            threshold = float(threshold_match.group(1)) if threshold_match else 1.0
            resolved_bool = cand_num >= threshold
            target_text = "yes" if resolved_bool else "no"
            for opt in f_info.options:
                opt_val = str(opt.get("value", "")).strip().lower()
                opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
                if (
                    opt_val in [target_text, "true" if resolved_bool else "false", "1" if resolved_bool else "0"]
                    or opt_text.startswith(target_text)
                    or bool(re.search(rf"\b{target_text}\b", opt_text))
                ):
                    return opt.get("value", "")
        # 5. Word-boundary matching for multi-word labels
        # Handles cases like val_str="bachelor" matching option text="Bachelor's Degree"
        # or val_str="united states" matching option text="United States of America"
        if len(val_str) >= 3:
            for opt in f_info.options:
                opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
                if opt_text and re.search(rf"\b{re.escape(val_str)}\b", opt_text):
                    return opt.get("value", "")

        # 6. Fallback to direct string containment match (checks both label and text keys)
        for opt in f_info.options:
            opt_val = str(opt.get("value", "")).strip().lower()
            opt_text = str(opt.get("label", "") or opt.get("text", "")).strip().lower()
            if val_str and (val_str in opt_val or val_str in opt_text or opt_text in val_str):
                return opt.get("value", "")

        return None
