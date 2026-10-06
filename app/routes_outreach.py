"""Flask Blueprint defining REST API endpoints for Outreach Center."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from sqlalchemy import desc, func, select

from app.db.models import Application, Communication, FollowUp, Resume
from app.db.session import SessionLocal, get_db_session
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    FollowUpStatus,
    MessageStatus,
)
from app.services.outreach_service import OutreachService

logger = logging.getLogger(__name__)

outreach_bp = Blueprint("outreach", __name__, url_prefix="/api/outreach")
outreach_service = OutreachService()


@outreach_bp.route("/stats", methods=["GET"])
def get_outreach_stats():
    """Returns high-level metric counts for the Outreach Center dashboard."""
    try:
        stats = outreach_service.get_outreach_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error("Error computing outreach stats: %s", e)
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/templates", methods=["GET"])
def get_templates():
    """Lists email templates."""
    try:
        category = request.args.get("category")
        templates = outreach_service.list_templates(category=category)
        return jsonify(templates), 200
    except Exception as e:
        logger.error("Error listing templates: %s", e)
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/templates/<int:template_id>", methods=["GET"])
def get_template_detail(template_id: int):
    """Retrieves single template by ID."""
    try:
        t = outreach_service.get_template(template_id)
        if not t:
            return jsonify({"error": "Template not found"}), 404
        return jsonify(t), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/templates/preview", methods=["POST"])
def preview_template():
    """Previews template interpolation with given context dictionary."""
    try:
        payload = request.get_json(force=True) or {}
        template_id = int(payload.get("template_id", 0))
        context = payload.get("context", {})

        result = outreach_service.preview_template(template_id, context)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/send", methods=["POST"])
def send_outreach_email():
    """Dispatches a direct outreach application email."""
    try:
        data = request.get_json(force=True) or {}
        if not data.get("contact_email"):
            return jsonify({"error": "Contact email is required"}), 400

        sched_time_str = data.get("schedule_time")
        sched_time = None
        if sched_time_str:
            try:
                sched_time = datetime.fromisoformat(sched_time_str.replace("Z", "+00:00"))
                if sched_time.tzinfo is None:
                    sched_time = sched_time.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        dto = OutreachCreateDTO(
            account_id=data.get("account_id", "default"),
            job_id=data.get("job_id"),
            manual_job_title=data.get("manual_job_title") or data.get("job_title"),
            manual_company_name=data.get("manual_company_name") or data.get("company_name"),
            manual_job_url=data.get("manual_job_url") or data.get("job_url"),
            contact_id=data.get("contact_id"),
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_designation=data.get("contact_designation"),
            resume_id=data.get("resume_id"),
            template_id=data.get("template_id"),
            subject=data.get("subject", ""),
            body_text=data.get("body_text", ""),
            body_html=data.get("body_html"),
            schedule_time=sched_time,
            followup_cadence_days=data.get("followup_cadence_days", [4, 10, 17]),
            override_duplicate=bool(data.get("override_duplicate", False)),
        )


        sender_name = data.get("sender_name")
        sender_email = data.get("sender_email")

        result = outreach_service.send_outreach(dto, sender_name=sender_name, sender_email=sender_email)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error("Error sending outreach: %s", e)
        return jsonify({"error": str(e), "success": False}), 500


@outreach_bp.route("/conversations", methods=["GET"])
def list_conversations():
    """Lists recent outreach conversations."""
    try:
        state_filter = request.args.get("state")
        limit = int(request.args.get("limit", 50))
        conversations = outreach_service.list_conversations(state_filter=state_filter, limit=limit)
        return jsonify(conversations), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/conversations/<int:application_id>/timeline", methods=["GET"])
def get_timeline(application_id: int):
    """Retrieves full communication and follow-up timeline for an application."""
    try:
        timeline = outreach_service.get_conversation_timeline(application_id)
        if "error" in timeline:
            return jsonify(timeline), 404
        return jsonify(timeline), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/conversations/<int:application_id>/pause", methods=["POST"])
def pause_followups(application_id: int):
    """Pauses follow-up cadence for an application."""
    try:
        payload = request.get_json(force=True) or {}
        reason = payload.get("reason", "Manual user pause")
        count = outreach_service.pause_followups(application_id, reason=reason)
        return jsonify({"paused_count": count, "message": f"Paused {count} follow-ups"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/conversations/<int:application_id>/resume", methods=["POST"])
def resume_followups(application_id: int):
    """Resumes paused follow-up cadence for an application."""
    try:
        count = outreach_service.resume_followups(application_id)
        return jsonify({"resumed_count": count, "message": f"Resumed {count} follow-ups"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/followups/due", methods=["GET"])
def get_due_followups():
    """Lists all follow-ups that have become due."""
    try:
        due = outreach_service.list_due_followups()
        return jsonify(due), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/provider/test", methods=["POST"])
def test_provider():
    """Tests connectivity to configured email provider."""
    try:
        payload = request.get_json(force=True) or {}
        account_id = payload.get("account_id", "default")
        res = outreach_service.test_provider_connection(account_id)
        return jsonify({
            "success": res.success,
            "provider_name": res.provider_name,
            "message": res.message,
            "account_email": res.account_email,
            "tested_at": res.tested_at.isoformat() if res.tested_at else None,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@outreach_bp.route("/resumes", methods=["GET"])
def list_managed_resumes():
    """Lists available resumes for outreach without exposing physical storage paths."""
    try:
        with get_db_session(SessionLocal) as s:
            resumes = s.execute(
                select(Resume).where(Resume.is_archived == False).order_by(desc(Resume.is_default))
            ).scalars().all()
            items = [
                {
                    "id": r.id,
                    "name": r.name,
                    "version": r.version,
                    "role_target": r.role_target,
                    "is_default": r.is_default,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in resumes
            ]
            return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/sync", methods=["POST"])
def sync_mailbox():
    """Triggers an on-demand inbound mailbox synchronization."""
    try:
        from app.services.inbound_sync_service import InboundSyncService
        payload = request.get_json(force=True) or {}
        account_id = payload.get("account_id", "default")
        sync_svc = InboundSyncService(outreach_service=outreach_service)
        result = sync_svc.sync_mailbox(account_id=account_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@outreach_bp.route("/followups/<int:followup_id>/draft", methods=["GET"])
def get_followup_draft(followup_id: int):
    """Generates suggested follow-up subject and body text."""
    try:
        from app.services.followup_scheduler import FollowUpScheduler
        scheduler = FollowUpScheduler()
        draft = scheduler.prepare_followup_draft(followup_id)
        if "error" in draft:
            return jsonify(draft), 404
        return jsonify(draft), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/followups/<int:followup_id>/execute", methods=["POST"])
def execute_followup(followup_id: int):
    """Dispatches a follow-up email and updates its status to COMPLETED."""
    try:
        from app.services.followup_scheduler import FollowUpScheduler
        payload = request.get_json(force=True) or {}
        custom_subj = payload.get("subject")
        custom_body = payload.get("body_text")

        scheduler = FollowUpScheduler()
        result = scheduler.execute_followup(
            followup_id=followup_id,
            custom_subject=custom_subj,
            custom_body=custom_body,
        )
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@outreach_bp.route("/followups/refresh", methods=["POST"])
def refresh_due_followups():
    """Refreshes status of follow-ups that have become due."""
    try:
        from app.services.followup_scheduler import FollowUpScheduler
        scheduler = FollowUpScheduler()
        count = scheduler.refresh_due_statuses()
        return jsonify({"updated_count": count, "message": f"Updated {count} follow-ups to DUE"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/ai/generate", methods=["POST"])
@outreach_bp.route("/ai/generate-pitch", methods=["POST"])
def generate_ai_pitch():
    """Generates a tailored outreach email pitch using AI with template fallback."""
    try:
        from app.services.outreach_ai_service import OutreachAIService
        payload = request.get_json(force=True) or {}
        comp_name = payload.get("company_name", "")
        job_title = payload.get("job_title", "")
        recruiter_name = payload.get("recruiter_name")
        resume_id = payload.get("resume_id")
        tone = payload.get("tone", "direct")

        ai_svc = OutreachAIService()
        result = ai_svc.generate_pitch(
            company_name=comp_name,
            job_title=job_title,
            recruiter_name=recruiter_name,
            resume_id=resume_id,
            tone=tone,
        )
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outreach_bp.route("/analytics", methods=["GET"])
def get_outreach_analytics():
    """Retrieves conversion funnel metrics and template performance statistics."""
    try:
        from app.services.outreach_analytics_service import OutreachAnalyticsService
        analytics_svc = OutreachAnalyticsService()
        metrics = analytics_svc.get_funnel_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        logger.error("Error computing outreach analytics: %s", e)
        return jsonify({"error": str(e)}), 500


@outreach_bp.route("/ai/classify-response", methods=["POST"])
def classify_inbound_response():
    """Classifies an incoming recruiter email to categorize it and suggest actions."""
    try:
        from app.services.outreach_ai_service import OutreachAIService
        payload = request.get_json(force=True) or {}
        body_text = payload.get("body_text") or payload.get("email_body") or ""
        subject = payload.get("subject") or payload.get("email_subject") or ""

        ai_svc = OutreachAIService()
        classification = ai_svc.classify_response(email_body=body_text, email_subject=subject)
        return jsonify({"success": True, **classification}), 200
    except Exception as e:
        logger.error("Error classifying inbound email: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@outreach_bp.route("/conversations/<int:app_id>/apply-status", methods=["POST"])
def apply_application_status(app_id: int):
    """Updates application status with human confirmation guardrail."""
    try:
        payload = request.get_json(force=True) or {}
        new_status = payload.get("status")
        notes = payload.get("notes", "")

        if not new_status:
            return jsonify({"error": "status is required"}), 400

        with get_db_session(SessionLocal) as s:
            app = s.get(Application, app_id)
            if not app:
                return jsonify({"error": f"Application {app_id} not found"}), 404
            
            app.status = new_status
            if notes:
                app.notes = f"{app.notes or ''}\n[Status Change]: {notes}".strip()
            s.commit()

        return jsonify({
            "success": True,
            "new_status": new_status,
            "message": f"Application updated to {new_status}",
        }), 200
    except Exception as e:
        logger.error("Error updating application status: %s", e)
        return jsonify({"error": str(e)}), 500





