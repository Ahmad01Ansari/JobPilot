"""Outreach Center Analytics and Conversion Funnel Engine."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Application,
    Communication,
    EmailTemplate,
    FollowUp,
)
from app.db.session import SessionLocal, get_db_session
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    FollowUpStatus,
    MessageStatus,
)

logger = logging.getLogger(__name__)


class OutreachAnalyticsService:
    """Calculates production email outreach funnels, reply velocity, and template conversion rates."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def get_funnel_metrics(self) -> Dict[str, Any]:
        """Calculates end-to-end recruitment funnel for cold outreach."""
        with get_db_session(self._session_factory) as s:
            # 1. Volume metrics
            total_apps = s.execute(
                select(func.count(Application.id)).where(
                    Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL
                )
            ).scalar() or 0

            outbound_sent = s.execute(
                select(func.count(Communication.id)).where(
                    Communication.direction == "OUTBOUND",
                    Communication.status == MessageStatus.SENT.value,
                )
            ).scalar() or 0

            outbound_failed = s.execute(
                select(func.count(Communication.id)).where(
                    Communication.direction == "OUTBOUND",
                    Communication.status == MessageStatus.FAILED.value,
                )
            ).scalar() or 0

            # 2. Inbound replies
            replied_app_ids = set(
                s.execute(
                    select(Communication.application_id)
                    .where(Communication.direction == "INBOUND")
                    .distinct()
                ).scalars().all()
            )
            total_replied = len([aid for aid in replied_app_ids if aid is not None])

            # 3. Interview & Offer conversion
            interviews_scheduled = s.execute(
                select(func.count(Application.id)).where(
                    Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL,
                    Application.status.in_(["INTERVIEW", "ASSESSMENT"]),
                )
            ).scalar() or 0

            offers_received = s.execute(
                select(func.count(Application.id)).where(
                    Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL,
                    Application.status == "OFFER",
                )
            ).scalar() or 0

            # Reply rate and delivery rate calculations
            total_dispatched = outbound_sent + outbound_failed
            delivery_rate = round((outbound_sent / total_dispatched) * 100, 1) if total_dispatched > 0 else 100.0
            reply_rate = round((total_replied / total_apps) * 100, 1) if total_apps > 0 else 0.0
            interview_rate = round((interviews_scheduled / total_apps) * 100, 1) if total_apps > 0 else 0.0

            # 4. Reply velocity (Average hours from first outbound to first inbound reply)
            velocity_hours: List[float] = []
            for app_id in replied_app_ids:
                if not app_id:
                    continue
                first_out = s.execute(
                    select(Communication.occurred_at)
                    .where(
                        Communication.application_id == app_id,
                        Communication.direction == "OUTBOUND",
                        Communication.status == MessageStatus.SENT.value,
                    )
                    .order_by(Communication.occurred_at.asc())
                ).scalars().first()

                first_in = s.execute(
                    select(Communication.occurred_at)
                    .where(
                        Communication.application_id == app_id,
                        Communication.direction == "INBOUND",
                    )
                    .order_by(Communication.occurred_at.asc())
                ).scalars().first()

                if first_out and first_in and first_in > first_out:
                    delta = (first_in - first_out).total_seconds() / 3600.0
                    velocity_hours.append(delta)

            avg_reply_hours = round(sum(velocity_hours) / len(velocity_hours), 1) if velocity_hours else None

            # 5. Follow-up cadence status breakdown
            followup_stats = {
                "pending": s.execute(
                    select(func.count(FollowUp.id)).where(FollowUp.status == FollowUpStatus.PENDING.value)
                ).scalar() or 0,
                "due": s.execute(
                    select(func.count(FollowUp.id)).where(FollowUp.status == FollowUpStatus.DUE.value)
                ).scalar() or 0,
                "completed": s.execute(
                    select(func.count(FollowUp.id)).where(FollowUp.status == FollowUpStatus.COMPLETED.value)
                ).scalar() or 0,
                "paused": s.execute(
                    select(func.count(FollowUp.id)).where(FollowUp.status == FollowUpStatus.PAUSED.value)
                ).scalar() or 0,
            }

            # 6. Template Performance Ranking
            templates = s.execute(select(EmailTemplate)).scalars().all()
            template_rankings = []
            for tmpl in templates:
                sent_count = s.execute(
                    select(func.count(Communication.id)).where(
                        Communication.template_id == tmpl.id,
                        Communication.direction == "OUTBOUND",
                        Communication.status == MessageStatus.SENT.value,
                    )
                ).scalar() or 0

                tmpl_app_ids = set(
                    s.execute(
                        select(Communication.application_id).where(
                            Communication.template_id == tmpl.id,
                            Communication.direction == "OUTBOUND",
                        )
                    ).scalars().all()
                )
                tmpl_replied = len(tmpl_app_ids.intersection(replied_app_ids))
                tmpl_reply_rate = round((tmpl_replied / sent_count) * 100, 1) if sent_count > 0 else 0.0

                template_rankings.append({
                    "template_id": tmpl.id,
                    "template_name": tmpl.name,
                    "category": tmpl.category,
                    "sent_count": sent_count,
                    "replied_count": tmpl_replied,
                    "reply_rate": tmpl_reply_rate,
                })

            template_rankings.sort(key=lambda x: x["reply_rate"], reverse=True)

            return {
                "total_outreach_applications": total_apps,
                "outbound_sent": outbound_sent,
                "outbound_failed": outbound_failed,
                "delivery_success_rate": delivery_rate,
                "recruiter_replied_count": total_replied,
                "reply_rate": reply_rate,
                "average_reply_time_hours": avg_reply_hours,
                "interviews_scheduled": interviews_scheduled,
                "interview_rate": interview_rate,
                "offers_received": offers_received,
                "followup_cadence_breakdown": followup_stats,
                "template_performance": template_rankings,
            }
