"""Repository for managing EmailTemplate entities and seeding canonical templates."""

import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.email_template import EmailTemplate
from app.services.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

CANONICAL_DEFAULT_TEMPLATES = [
    {
        "key": "direct_application_pitch",
        "name": "Direct Application Pitch",
        "category": "JOB_APPLICATION",
        "subject_template": "Application: {{job_title}} - {{candidate_name}}",
        "body_template": (
            "Hi {{recruiter_name}},\n\n"
            "I noticed that {{company_name}} is hiring for a {{job_title}}, and I wanted to reach out directly to express my strong interest in the role.\n\n"
            "With over {{years_of_experience}} years of experience specializing in {{skills}}, I have a track record of driving technical impact and delivering robust solutions.\n\n"
            "I have attached my resume for your review. You can also view my portfolio and work samples at {{portfolio_url}}.\n\n"
            "Would you be open to a brief 10-minute introductory call next week?\n\n"
            "Best regards,\n"
            "{{candidate_name}}\n"
            "{{candidate_email}}\n"
            "{{candidate_phone}}"
        ),
    },
    {
        "key": "followup_step_1_checkin",
        "name": "Follow-Up 1: Polite Check-in",
        "category": "FOLLOW_UP",
        "subject_template": "Following up: Application for {{job_title}} - {{candidate_name}}",
        "body_template": (
            "Hi {{recruiter_name}},\n\n"
            "I hope you are having a productive week.\n\n"
            "I wanted to follow up on the application I submitted last week for the {{job_title}} position at {{company_name}}.\n\n"
            "I remain very enthusiastic about the team's mission and would love the opportunity to discuss how my background in {{skills}} aligns with your needs.\n\n"
            "Looking forward to hearing from you.\n\n"
            "Warm regards,\n"
            "{{candidate_name}}"
        ),
    },
    {
        "key": "followup_step_2_value_add",
        "name": "Follow-Up 2: Value-Add & Project Highlights",
        "category": "FOLLOW_UP",
        "subject_template": "Quick follow-up / Project insight: {{job_title}} role",
        "body_template": (
            "Hi {{recruiter_name}},\n\n"
            "Following up on my previous note regarding the {{job_title}} role at {{company_name}}.\n\n"
            "I recently deployed an architecture addressing similar scalability challenges using {{skills}}, which you can explore in detail here: {{portfolio_url}}.\n\n"
            "I would welcome the chance to share how these techniques could benefit {{company_name}}.\n\n"
            "Best,\n"
            "{{candidate_name}}"
        ),
    },
    {
        "key": "followup_step_3_graceful_closeout",
        "name": "Follow-Up 3: Graceful Closeout",
        "category": "FOLLOW_UP",
        "subject_template": "Final check-in: {{job_title}} at {{company_name}}",
        "body_template": (
            "Hi {{recruiter_name}},\n\n"
            "I know your team is busy, so I will keep this very brief.\n\n"
            "I assume the timeline or priorities for the {{job_title}} position at {{company_name}} may have shifted, so I will pause my follow-ups for now.\n\n"
            "If another relevant opportunity opens up where my expertise in {{skills}} could be of value, please do not hesitate to keep my information on file.\n\n"
            "Wishing you and {{company_name}} continued success!\n\n"
            "Best regards,\n"
            "{{candidate_name}}"
        ),
    },
]


class EmailTemplateRepository:
    """Data access repository for email templates."""

    def __init__(self, session: Session):
        self.session = session

    def list_all(
        self,
        include_inactive: bool = False,
        category: Optional[str] = None,
    ) -> List[EmailTemplate]:
        """Lists templates with optional filtering by active status and category."""
        stmt = select(EmailTemplate)
        if not include_inactive:
            stmt = stmt.where(EmailTemplate.is_active == True)
        if category:
            stmt = stmt.where(EmailTemplate.category == category)
        stmt = stmt.order_by(EmailTemplate.name)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_id(self, template_id: int) -> Optional[EmailTemplate]:
        return self.session.get(EmailTemplate, template_id)

    def get_by_key(self, key: str) -> Optional[EmailTemplate]:
        stmt = select(EmailTemplate).where(EmailTemplate.key == key)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        key: str,
        name: str,
        subject_template: str,
        body_template: str,
        category: str = "JOB_APPLICATION",
        is_active: bool = True,
    ) -> EmailTemplate:
        extracted = TemplateRenderer.extract_variables(f"{subject_template} {body_template}")
        tmpl = EmailTemplate(
            key=key,
            name=name,
            category=category,
            subject_template=subject_template,
            body_template=body_template,
            variables_json=json.dumps(extracted),
            is_active=is_active,
        )
        self.session.add(tmpl)
        self.session.flush()
        return tmpl

    def update(
        self,
        template_id: int,
        name: Optional[str] = None,
        subject_template: Optional[str] = None,
        body_template: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[EmailTemplate]:
        tmpl = self.get_by_id(template_id)
        if not tmpl:
            return None

        if name is not None:
            tmpl.name = name
        if subject_template is not None:
            tmpl.subject_template = subject_template
        if body_template is not None:
            tmpl.body_template = body_template
        if category is not None:
            tmpl.category = category
        if is_active is not None:
            tmpl.is_active = is_active

        extracted = TemplateRenderer.extract_variables(f"{tmpl.subject_template} {tmpl.body_template}")
        tmpl.variables_json = json.dumps(extracted)

        self.session.flush()
        return tmpl

    def delete(self, template_id: int) -> bool:
        """Deletes a template by its ID."""
        tmpl = self.get_by_id(template_id)
        if not tmpl:
            return False
        self.session.delete(tmpl)
        self.session.flush()
        return True

    def duplicate(self, template_id: int) -> Optional[EmailTemplate]:
        """Duplicates an existing template with a new key and copy name."""
        import uuid
        tmpl = self.get_by_id(template_id)
        if not tmpl:
            return None
        new_key = f"{tmpl.key}_copy_{uuid.uuid4().hex[:6]}"
        new_name = f"{tmpl.name} (Copy)"
        return self.create(
            key=new_key,
            name=new_name,
            subject_template=tmpl.subject_template,
            body_template=tmpl.body_template,
            category=tmpl.category,
            is_active=tmpl.is_active,
        )

    def seed_defaults_if_empty(self) -> int:
        """Populates the database with canonical templates if none exist."""
        existing_count = self.session.execute(select(EmailTemplate)).scalars().all()
        if existing_count:
            return 0

        created = 0
        for item in CANONICAL_DEFAULT_TEMPLATES:
            self.create(
                key=item["key"],
                name=item["name"],
                category=item["category"],
                subject_template=item["subject_template"],
                body_template=item["body_template"],
            )
            created += 1

        self.session.commit()
        logger.info("Seeded %d canonical email templates into database.", created)
        return created
