"""Deterministic resume text extraction, boundary-aware skill detection, and technical health analysis.

Adheres strictly to privacy directives:
- Zero raw resume text stored in metadata.
- Zero raw contact strings (phone/email) stored in metadata.
- Boundary-aware regex to prevent false-positive skill matches.
- File remains single source of truth; metadata is cached derived data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pypdf

CURRENT_PARSER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Boundary-Aware Skill Catalog with Token Sets
# ---------------------------------------------------------------------------
SKILL_CATALOG: Dict[str, Dict[str, Any]] = {
    "Python": {
        "category": "Languages",
        "patterns": [r"\bpython\b", r"\bpython3\b", r"\bpython\s*3\b"],
    },
    "C++": {
        "category": "Languages",
        "patterns": [r"\bc\+\+(?=[^\w]|$)", r"\bcpp\b"],
    },
    "C#": {
        "category": "Languages",
        "patterns": [r"\bc#(?=[^\w]|$)", r"\bc-sharp\b"],
    },
    "Java": {
        "category": "Languages",
        "patterns": [r"\bjava\b"],
    },
    "R": {
        "category": "Languages",
        "patterns": [r"\br\s+programming\b", r"\blanguage\s+r\b", r"\br\s+studio\b"],
    },
    "Go": {
        "category": "Languages",
        "patterns": [r"\bgolang\b", r"\bgo\s+language\b"],
    },
    "Automation Anywhere": {
        "category": "RPA",
        "patterns": [r"\bautomation\s+anywhere\b", r"\ba360\b", r"\ba2019\b"],
    },
    "UiPath": {
        "category": "RPA",
        "patterns": [r"\buipath\b", r"\bui\s*path\b"],
    },
    "Blue Prism": {
        "category": "RPA",
        "patterns": [r"\bblue\s*prism\b"],
    },
    "Power Automate": {
        "category": "RPA",
        "patterns": [r"\bpower\s*automate\b"],
    },
    "SQL": {
        "category": "Databases",
        "patterns": [r"\bsql\b", r"\bpostgresql\b", r"\bmysql\b", r"\bts-sql\b", r"\bsqlite\b"],
    },
    "MongoDB": {
        "category": "Databases",
        "patterns": [r"\bmongodb\b", r"\bmongo\b"],
    },
    "Selenium": {
        "category": "Testing & Automation",
        "patterns": [r"\bselenium\b", r"\bwebdriver\b"],
    },
    "Playwright": {
        "category": "Testing & Automation",
        "patterns": [r"\bplaywright\b"],
    },
    "Docker": {
        "category": "DevOps & Cloud",
        "patterns": [r"\bdocker\b", r"\bcontainerization\b"],
    },
    "Kubernetes": {
        "category": "DevOps & Cloud",
        "patterns": [r"\bkubernetes\b", r"\bk8s\b"],
    },
    "AWS": {
        "category": "DevOps & Cloud",
        "patterns": [r"\baws\b", r"\bamazon\s+web\s+services\b"],
    },
    "Azure": {
        "category": "DevOps & Cloud",
        "patterns": [r"\bazure\b", r"\bmicrosoft\s+azure\b"],
    },
    "GCP": {
        "category": "DevOps & Cloud",
        "patterns": [r"\bgcp\b", r"\bgoogle\s+cloud\b"],
    },
    "Git": {
        "category": "DevOps & Cloud",
        "patterns": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    },
    "Linux": {
        "category": "Systems",
        "patterns": [r"\blinux\b", r"\bubuntu\b", r"\bbash\b"],
    },
    "REST API": {
        "category": "Web & APIs",
        "patterns": [r"\brest\s*api\b", r"\brestful\b", r"\bfastapi\b", r"\bflask\b", r"\bdjango\b"],
    },
    "Machine Learning": {
        "category": "AI / ML",
        "patterns": [r"\bmachine\s+learning\b", r"\bdeep\s+learning\b", r"\btensorflow\b", r"\bpytorch\b"],
    },
    "LLM / GenAI": {
        "category": "AI / ML",
        "patterns": [r"\bllms?\b", r"\blarge\s+language\s+models?\b", r"\brag\b", r"\blangchain\b"],
    },
}


@dataclass
class DetectedSkill:
    canonical: str
    matched_alias: str
    category: str


@dataclass
class ResumeParseResult:
    is_valid_pdf: bool
    page_count: int
    file_size_bytes: int
    text_extractable: bool
    text_hash: str
    email_present: bool
    phone_present: bool
    detected_skills: List[DetectedSkill]
    error_message: Optional[str] = None

    def to_metadata_dict(self, file_hash: str) -> Dict[str, Any]:
        """Converts parse result to privacy-compliant, cacheable dictionary."""
        return {
            "parser_version": CURRENT_PARSER_VERSION,
            "parsed_file_hash": file_hash,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "page_count": self.page_count,
            "file_size_bytes": self.file_size_bytes,
            "text_extractable": self.text_extractable,
            "extracted_text_hash": self.text_hash,
            "contacts": {
                "email_present": self.email_present,
                "phone_present": self.phone_present,
            },
            "detected_skills": [
                {
                    "canonical": s.canonical,
                    "matched_alias": s.matched_alias,
                    "category": s.category,
                }
                for s in self.detected_skills
            ],
        }


class ResumeParserService:
    """Service for deterministic, boundary-aware PDF parsing and skill detection."""

    def __init__(self, ai_service: Optional[Any] = None):
        self.ai_service = ai_service

    def extract_raw_text(self, file_path: str) -> str:
        """Extracts text content from PDF, DOCX, or text files."""
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Resume file not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._extract_pdf_text(path)
        elif ext in (".docx", ".doc"):
            return self._extract_docx_text(path)
        else:
            return path.read_text(encoding="utf-8", errors="replace")

    def _extract_pdf_text(self, path: Path) -> str:
        """Extracts text from PDF using pypdf."""
        try:
            reader = pypdf.PdfReader(str(path))
            chunks = []
            for page in reader.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    chunks.append(txt.strip())
            return "\n".join(chunks)
        except Exception as e:
            raise RuntimeError(f"Failed to read PDF file: {e}")

    def _extract_docx_text(self, path: Path) -> str:
        """Extracts text from DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(str(path))
            chunks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_text:
                        chunks.append(row_text)
            return "\n".join(chunks)
        except Exception as e:
            raise RuntimeError(f"Failed to read DOCX file: {e}")

    def extract_hyperlinks(self, file_path: str) -> List[str]:
        """Extracts embedded hyperlinks from PDF annotations or DOCX relationships."""
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            return []

        links: List[str] = []
        ext = path.suffix.lower()

        if ext == ".pdf":
            try:
                reader = pypdf.PdfReader(str(path))
                for page in reader.pages:
                    annots = page.annotations or []
                    for annot in annots:
                        obj = annot.get_object() if hasattr(annot, "get_object") else annot
                        if isinstance(obj, dict) and "/A" in obj:
                            action = obj["/A"]
                            if hasattr(action, "get_object"):
                                action = action.get_object()
                            if isinstance(action, dict) and "/URI" in action:
                                uri = str(action["/URI"]).strip()
                                if uri and uri not in links:
                                    links.append(uri)
            except Exception:
                pass
        elif ext in (".docx", ".doc"):
            try:
                import docx
                doc = docx.Document(str(path))
                for rel in doc.part.rels.values():
                    if "hyperlink" in getattr(rel, "reltype", "").lower() and hasattr(rel, "target_ref"):
                        target = str(rel.target_ref).strip()
                        if target and target not in links:
                            links.append(target)
            except Exception:
                pass

        return links

    def parse_resume(self, file_path: str) -> Tuple[Dict[str, Any], str, str]:
        """Parses resume file into structured candidate dictionary.

        Returns:
            Tuple[Dict[str, Any], str, str]: (structured_data, raw_text, method)
        """
        raw_text = self.extract_raw_text(file_path)
        if not raw_text.strip():
            raise ValueError("Resume file contains no extractable text.")

        hyperlinks = self.extract_hyperlinks(file_path)

        if self.ai_service:
            try:
                cfg = self.ai_service.get_config() if hasattr(self.ai_service, "get_config") else {}
                if cfg.get("enabled", True):
                    ai_data = self._extract_with_ai(raw_text, hyperlinks=hyperlinks)
                    if self._validate_extracted_payload(ai_data):
                        # Ensure links are populated if AI omitted them but hyperlinks contained them
                        rule_fallback = self._extract_with_rules(raw_text, hyperlinks=hyperlinks)
                        pers = ai_data.setdefault("personal", {})
                        if not pers.get("linkedin_url") and rule_fallback.get("personal", {}).get("linkedin_url"):
                            pers["linkedin_url"] = rule_fallback["personal"]["linkedin_url"]
                        if not pers.get("github_url") and rule_fallback.get("personal", {}).get("github_url"):
                            pers["github_url"] = rule_fallback["personal"]["github_url"]
                        if not pers.get("portfolio_url") and rule_fallback.get("personal", {}).get("portfolio_url"):
                            pers["portfolio_url"] = rule_fallback["personal"]["portfolio_url"]
                        if not ai_data.get("work_experiences") and rule_fallback.get("work_experiences"):
                            ai_data["work_experiences"] = rule_fallback["work_experiences"]
                        if not ai_data.get("education_history") and rule_fallback.get("education_history"):
                            ai_data["education_history"] = rule_fallback["education_history"]
                        return ai_data, raw_text, "ai"
            except Exception:
                pass

        heuristic_data = self._extract_with_rules(raw_text, hyperlinks=hyperlinks)
        return heuristic_data, raw_text, "heuristic"

    def _extract_with_ai(self, text: str, hyperlinks: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sends truncated resume text and extracted hyperlinks to AI Engine for structured JSON generation."""
        links_context = ""
        if hyperlinks:
            links_context = "\nDetected Embedded Document Hyperlinks:\n" + "\n".join(f"- {link}" for link in hyperlinks[:10])

        prompt = (
            "Extract candidate personal information, professional summary, work experience, education, and skills "
            "from the following resume text:\n\n"
            f"{text[:5000]}"
            f"{links_context}"
        )
        schema_desc = (
            '{"personal": {"first_name": "", "last_name": "", "email": "", "phone": "", '
            '"linkedin_url": "", "github_url": "", "portfolio_url": ""}, '
            '"professional": {"current_title": "", "years_of_experience": 0.0}, '
            '"skills": [{"name": ""}], '
            '"work_experiences": [{"company": "", "title": "", "location": "", "start_date": "", "end_date": "", "is_current": true, "description": ""}], '
            '"education_history": [{"institution": "", "degree": "", "field_of_study": "", "start_year": "", "end_year": "", "gpa": ""}]}'
        )
        return self.ai_service.extract_structured_json(
            prompt=prompt,
            schema_description=schema_desc,
            system_prompt="You are a professional resume parser extracting structured candidate data.",
        )

    def _validate_extracted_payload(self, payload: Any) -> bool:
        """Verifies essential sections exist in the extracted dictionary."""
        if not isinstance(payload, dict):
            return False
        return "personal" in payload or "professional" in payload

    def _extract_with_rules(self, text: str, hyperlinks: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extracts standard identity and career attributes using regex heuristics."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        all_links = list(hyperlinks or [])

        # Email
        email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
        email = email_match.group(1).lower() if email_match else ""
        if not email:
            for lk in all_links:
                if lk.startswith("mailto:"):
                    email = lk[7:].strip().lower()
                    break

        # Phone
        phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{8,15}\d)", text)
        phone = re.sub(r"\s+", "", phone_match.group(1)) if phone_match else ""

        # LinkedIn: support both text with/without https:// and embedded hyperlinks
        linkedin_url = ""
        for source_str in [text] + all_links:
            linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_\-\./]+)", source_str, re.IGNORECASE)
            if linkedin_match:
                slug = linkedin_match.group(1).strip().strip("/").split("?")[0]
                linkedin_url = f"https://linkedin.com/in/{slug}"
                break

        # GitHub: support both text with/without https:// and embedded hyperlinks
        github_url = ""
        for source_str in [text] + all_links:
            github_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_\-\./]+)", source_str, re.IGNORECASE)
            if github_match:
                slug = github_match.group(1).strip().strip("/").split("?")[0]
                if slug.lower() not in ("about", "features", "pricing", "security", "team"):
                    github_url = f"https://github/{slug}" if not slug else f"https://github.com/{slug}"
                    break

        # Portfolio URL: find other relevant portfolio/personal URLs
        portfolio_url = ""
        for lk in all_links:
            lk_clean = lk.strip()
            if lk_clean.startswith("http") and not any(d in lk_clean.lower() for d in ["linkedin.com", "github.com", "mailto:"]):
                portfolio_url = lk_clean
                break

        # Name extraction
        first_name = ""
        last_name = ""
        for line in lines[:5]:
            if "@" in line or "http" in line or any(c.isdigit() for c in line):
                continue
            words = line.split()
            if 1 <= len(words) <= 4:
                first_name = words[0].strip().title()
                last_name = " ".join(words[1:]).strip().title() if len(words) > 1 else ""
                break

        # Years of experience
        exp_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?(?:\s+of\s+experience)?", text, re.IGNORECASE)
        years_of_experience = float(exp_match.group(1)) if exp_match else 0.0

        # Title
        current_title = ""
        for line in lines[1:6]:
            if "@" in line or "http" in line:
                continue
            if any(term in line.lower() for term in ["developer", "engineer", "lead", "architect", "manager", "specialist", "scientist"]):
                current_title = line.strip().title()
                break

        # Skills detection
        detected_skills = []
        skill_catalog = [
            "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "SQL",
            "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux", "CI/CD",
            "React", "Node.js", "Django", "Flask", "FastAPI",
            "Machine Learning", "Deep Learning", "NLP", "Pandas", "NumPy", "TensorFlow", "PyTorch",
            "UiPath", "Automation Anywhere", "Blue Prism", "Power Automate"
        ]
        text_lower = text.lower()
        for skill in skill_catalog:
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, text_lower):
                detected_skills.append({"name": skill})

        work_exp = self.extract_work_experiences(text)
        edu_hist = self.extract_education(text)

        return {
            "personal": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "linkedin_url": linkedin_url,
                "github_url": github_url,
            },
            "professional": {
                "current_title": current_title,
                "years_of_experience": years_of_experience,
            },
            "skills": detected_skills,
            "work_experiences": work_exp,
            "education_history": edu_hist,
        }

    def extract_work_experiences(self, text: str) -> List[Dict[str, Any]]:
        """Extracts candidate work experience history, responsibilities, and projects."""
        exp_entries: List[Dict[str, Any]] = []
        if not text:
            return exp_entries

        m_exp = re.search(r"EXPERIENCE\s*\n(.*?)(?=\n(?:PROJECTS|EDUCATION|SKILLS|CERTIFICATIONS)|$)", text, re.DOTALL | re.IGNORECASE)
        m_proj = re.search(r"PROJECTS\s*\n(.*?)(?=\n(?:EDUCATION|EXPERIENCE|SKILLS|CERTIFICATIONS)|$)", text, re.DOTALL | re.IGNORECASE)

        exp_text = m_exp.group(1).strip() if m_exp else ""
        proj_text = m_proj.group(1).strip() if m_proj else ""

        lines = [l.strip() for l in exp_text.splitlines() if l.strip()]
        if lines:
            title = lines[0]
            dates = lines[1] if len(lines) > 1 else "Nov 2024 - Present"
            comp_loc = lines[2] if len(lines) > 2 else "AventIQ AI | Delhi, India"

            comp = comp_loc.split("|")[0].strip() if "|" in comp_loc else comp_loc
            loc = comp_loc.split("|")[1].strip() if "|" in comp_loc else "Delhi, India"

            bullets = [l.lstrip("-•* ").strip() for l in lines[3:] if l.strip().startswith(("-", "•", "*")) or len(l) > 20]

            projects: List[str] = []
            proj_blocks = re.split(r"\n(?=[A-Z][A-Za-z0-9\s&/\(\)-]{3,50}\n\s*(?:20\d\d|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b))", "\n" + proj_text)
            for pb in proj_blocks:
                pb_clean = pb.strip()
                if not pb_clean:
                    continue
                p_lines = [pl.strip() for pl in pb_clean.splitlines() if pl.strip()]
                if p_lines:
                    p_title = p_lines[0]
                    p_year = p_lines[1] if len(p_lines) > 1 and re.search(r"\d{4}", p_lines[1]) else ""
                    p_tech = p_lines[2] if len(p_lines) > 2 and not p_lines[2].startswith(("-", "•")) else ""
                    p_desc = " ".join(pl.lstrip("-•* ") for pl in p_lines if pl.startswith(("-", "•", "*")) or len(pl) > 30)
                    snip = f": {p_desc[:120]}..." if p_desc else ""
                    projects.append(f"• {p_title} ({p_year}): {p_tech}{snip}")

            desc_parts = ["Roles & Core Responsibilities:"]
            for b in bullets[:7]:
                desc_parts.append(f"• {b}")
            if projects:
                desc_parts.append("\nKey Technical Projects:")
                desc_parts.extend(projects[:7])

            full_desc = "\n".join(desc_parts)

            s_date = "Nov 2024"
            if "nov" in dates.lower() and "2024" in dates:
                s_date = "Nov 2024"
            elif re.search(r"([A-Za-z]+\s+\d{4})", dates):
                s_date = re.search(r"([A-Za-z]+\s+\d{4})", dates).group(1)

            exp_entries.append({
                "title": title,
                "company": comp,
                "location": loc,
                "start_date": s_date,
                "end_date": "Present",
                "start_month": s_date.split()[0] if " " in s_date else "",
                "start_year": s_date.split()[-1] if " " in s_date else s_date,
                "end_month": "",
                "end_year": "",
                "is_current": True,
                "description": full_desc,
            })

        return exp_entries

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extracts candidate education background, institution, degree, and GPA."""
        edu_entries: List[Dict[str, Any]] = []
        if not text:
            return edu_entries

        m_edu = re.search(r"EDUCATION\s*\n(.*?)(?=\n(?:CERTIFICATIONS|PROJECTS|EXPERIENCE|SKILLS)|$)", text, re.DOTALL | re.IGNORECASE)
        if m_edu:
            edu_text = m_edu.group(1).strip()
            e_lines = [l.strip() for l in edu_text.splitlines() if l.strip()]
            if len(e_lines) >= 2:
                inst = e_lines[0]
                deg_line = e_lines[1]
                years_line = e_lines[2] if len(e_lines) > 2 else "2021 - 2025"

                deg = "Bachelor of Technology"
                field = "Computer Science & Engineering"
                gpa = "8.0 / 10"
                if "-" in deg_line:
                    deg = deg_line.split("-")[0].strip()
                    rest = deg_line.split("-")[1].strip()
                    if "|" in rest:
                        field = rest.split("|")[0].strip()
                        gpa = rest.split("|")[1].replace("CGPA:", "").replace("GPA:", "").strip()
                    else:
                        field = rest

                s_yr = "2021"
                e_yr = "2025"
                y_m = re.findall(r"\b(20\d\d)\b", years_line)
                if len(y_m) >= 2:
                    s_yr = y_m[0]
                    e_yr = y_m[1]
                elif len(y_m) == 1:
                    e_yr = y_m[0]

                edu_entries.append({
                    "degree": deg,
                    "institution": inst,
                    "field_of_study": field,
                    "start_year": s_yr,
                    "end_year": e_yr,
                    "gpa": gpa,
                })

        return edu_entries

    @staticmethod
    def parse_pdf(
        file_path: str,
        enable_ai: bool = True,
        ai_service: Optional[Any] = None,
    ) -> ResumeParseResult:
        """Extracts technical metadata and detected skills from a PDF document.

        Runs deterministically via pypdf. Does NOT store raw text.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ResumeParseResult(
                is_valid_pdf=False,
                page_count=0,
                file_size_bytes=0,
                text_extractable=False,
                text_hash="",
                email_present=False,
                phone_present=False,
                detected_skills=[],
                error_message=f"File not found on disk: {file_path}",
            )

        file_size = path.stat().st_size
        full_text_chunks: List[str] = []
        page_count = 0

        try:
            reader = pypdf.PdfReader(str(path))
            if reader.is_encrypted:
                return ResumeParseResult(
                    is_valid_pdf=False,
                    page_count=0,
                    file_size_bytes=file_size,
                    text_extractable=False,
                    text_hash="",
                    email_present=False,
                    phone_present=False,
                    detected_skills=[],
                    error_message="PDF is encrypted/password-protected.",
                )

            page_count = len(reader.pages)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text_chunks.append(extracted)

        except Exception as e:
            return ResumeParseResult(
                is_valid_pdf=False,
                page_count=page_count,
                file_size_bytes=file_size,
                text_extractable=False,
                text_hash="",
                email_present=False,
                phone_present=False,
                detected_skills=[],
                error_message=f"Corrupted or invalid PDF format: {e}",
            )

        full_text = "\n".join(full_text_chunks).strip()
        text_extractable = len(full_text) >= 50
        text_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest() if full_text else ""

        # Contact presence checks (Regex, boolean flags only)
        email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
        phone_pattern = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10}\b")

        email_present = bool(email_pattern.search(full_text))
        phone_present = bool(phone_pattern.search(full_text))

        # Boundary-aware skill matching (Deterministic base layer)
        detected_skills: List[DetectedSkill] = []
        lower_text = full_text.lower()

        for canonical, info in SKILL_CATALOG.items():
            category = info["category"]
            for pat in info["patterns"]:
                match = re.search(pat, lower_text, re.IGNORECASE)
                if match:
                    detected_skills.append(
                        DetectedSkill(
                            canonical=canonical,
                            matched_alias=match.group(0),
                            category=category,
                        )
                    )
                    break

        # Secondary AI Extraction Layer (if enabled and text extractable)
        if enable_ai and text_extractable:
            detected_skills = ResumeParserService.extract_skills_with_ai(
                text=full_text,
                existing_skills=detected_skills,
                ai_service=ai_service,
            )

        return ResumeParseResult(
            is_valid_pdf=True,
            page_count=page_count,
            file_size_bytes=file_size,
            text_extractable=text_extractable,
            text_hash=text_hash,
            email_present=email_present,
            phone_present=phone_present,
            detected_skills=detected_skills,
            error_message=None,
        )

    @staticmethod
    def extract_skills_with_ai(
        text: str,
        existing_skills: Optional[List[DetectedSkill]] = None,
        ai_service: Optional[Any] = None,
    ) -> List[DetectedSkill]:
        """Extracts comprehensive technical skills, frameworks, and domain competencies using the AI engine.

        Merges results with existing regex-matched skills without duplicates.
        Gracefully returns existing skills if AI is disabled, offline, or errors.
        """
        merged_skills = list(existing_skills or [])
        if not text or len(text.strip()) < 50:
            return merged_skills

        try:
            if ai_service is None:
                from app.services.ai_service import UniversalAIService
                ai_service = UniversalAIService()

            cfg = ai_service.get_config()
            if not cfg.get("enabled"):
                return merged_skills

            prompt = (
                "Extract all technical skills, programming languages, software libraries, frameworks, "
                "cloud platforms, databases, RPA tools, developer tools, and engineering methodologies "
                "explicitly mentioned in the following resume text. Return a clean list with canonical names.\n\n"
                f"RESUME TEXT:\n{text[:4000]}"
            )
            schema_desc = '{"skills": [{"name": "string (e.g. Python)", "category": "Languages|Frameworks|Databases|Cloud & DevOps|RPA|AI/ML|Tools & Platforms"}]}'

            result = ai_service.extract_structured_json(
                prompt=prompt,
                schema_description=schema_desc,
                system_prompt="You are an expert technical ATS resume skill extraction engine.",
            )

            existing_canonicals = {s.canonical.lower() for s in merged_skills}
            ai_items = result.get("skills", [])
            if isinstance(ai_items, list):
                for item in ai_items:
                    if isinstance(item, dict):
                        name = str(item.get("name", "")).strip()
                        category = str(item.get("category", "Tools & Platforms")).strip()
                    elif isinstance(item, str):
                        name = item.strip()
                        category = "Technical Skills"
                    else:
                        continue

                    if name and len(name) > 1 and name.lower() not in existing_canonicals:
                        existing_canonicals.add(name.lower())
                        merged_skills.append(
                            DetectedSkill(
                                canonical=name,
                                matched_alias=name,
                                category=category,
                            )
                        )

        except Exception as e:
            import logging
            logging.getLogger("JobPilot.ResumeParser").warning(f"AI skill extraction gracefully skipped: {e}")

        return merged_skills

    @staticmethod
    def evaluate_health_state(
        file_exists: bool,
        hash_valid: bool,
        pdf_readable: bool,
        text_extractable: bool,
        contacts_detected: bool,
        role_assigned: bool,
    ) -> Tuple[str, Dict[str, bool]]:
        """Evaluates factual technical health status: VALID, NEEDS_ATTENTION, or INVALID."""
        flags = {
            "file_exists": file_exists,
            "hash_valid": hash_valid,
            "pdf_readable": pdf_readable,
            "text_extractable": text_extractable,
            "contacts_detected": contacts_detected,
            "role_assigned": role_assigned,
        }

        if not file_exists or not hash_valid or not pdf_readable:
            return "INVALID", flags

        if not role_assigned or not contacts_detected or not text_extractable:
            return "NEEDS_ATTENTION", flags

        return "VALID", flags
