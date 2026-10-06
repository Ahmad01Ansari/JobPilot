from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import csv
from datetime import datetime
import os

from modules.tracker import ApplicationTracker, DEFAULT_TRACKER_PATH

_current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_current_dir, 'templates')):
    _root_dir = _current_dir
elif os.path.exists(os.path.join(os.path.dirname(_current_dir), 'templates')):
    _root_dir = os.path.dirname(_current_dir)
else:
    _root_dir = _current_dir

app = Flask(
    'jobpilot_dashboard',
    root_path=_root_dir,
    template_folder=os.path.join(_root_dir, 'templates'),
    static_folder=os.path.join(_root_dir, 'static')
)
CORS(app)

from app.routes_outreach import outreach_bp, outreach_service
app.register_blueprint(outreach_bp)

# Reconcile in-flight or overdue messages on startup
try:
    outreach_service.reconcile_startup_outreach()
except Exception as _e:
    pass


PATH = 'all excels/'
tracker = ApplicationTracker()

@app.route('/')
def home():
    """Displays the home page of the application."""
    return render_template('index.html')

@app.route('/applied-jobs', methods=['GET'])
def get_applied_jobs():
    '''
    Retrieves a list of applied jobs from the applications history CSV file.
    
    Returns a JSON response containing a list of jobs, each with details such as 
    Job ID, Title, Company, HR Name, HR Link, Job Link, External Job link, and Date Applied.
    
    If the CSV file is not found, returns a 404 error with a relevant message.
    If any other exception occurs, returns a 500 error with the exception message.
    '''

    try:
        jobs = []
        # First check database / tracker SSOT for submitted LinkedIn applications
        records = tracker.get_all_records(platform="linkedin", status="SUBMITTED")
        if records:
            for r in records:
                jobs.append({
                    'Job_ID': r.job_id,
                    'Title': r.title,
                    'Company': r.company,
                    'HR_Name': '',
                    'HR_Link': '',
                    'Job_Link': r.source_url,
                    'External_Job_link': r.source_url if r.application_type == "EXTERNAL" else "Easy Applied",
                    'Date_Applied': r.applied_at or r.discovered_at or ''
                })
            return jsonify(jobs)

        # Fallback to legacy CSV file if tracker has no records
        csv_file = PATH + 'all_applied_applications_history.csv'
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    jobs.append({
                        'Job_ID': row.get('Job ID', ''),
                        'Title': row.get('Title', ''),
                        'Company': row.get('Company', ''),
                        'HR_Name': row.get('HR Name', ''),
                        'HR_Link': row.get('HR Link', ''),
                        'Job_Link': row.get('Job Link', ''),
                        'External_Job_link': row.get('External Job link', ''),
                        'Date_Applied': row.get('Date Applied', '')
                    })
            return jsonify(jobs)
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/applied-jobs/<job_id>', methods=['PUT'])
def update_applied_date(job_id):
    """
    Updates the 'Date Applied' field of a job in the applications history CSV file.

    Args:
        job_id (str): The Job ID of the job to be updated.

    Returns:
        A JSON response with a message indicating success or failure of the update
        operation. If the job is not found, returns a 404 error with a relevant
        message. If any other exception occurs, returns a 500 error with the
        exception message.
    """
    try:
        data = []
        csvPath = PATH + 'all_applied_applications_history.csv'
        
        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404
            
        # Read current CSV content
        with open(csvPath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldNames = reader.fieldnames
            found = False
            for row in reader:
                if row['Job ID'] == job_id:
                    row['Date Applied'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    found = True
                data.append(row)
        
        if not found:
            return jsonify({"error": f"Job ID {job_id} not found"}), 404

        with open(csvPath, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldNames)
            writer.writeheader()
            writer.writerows(data)
        
        return jsonify({"message": "Date Applied updated successfully"}), 200
    except Exception as e:
        print(f"Error updating applied date: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500


# --- Phase 17: Naukri & Unified Application History Endpoints ---

@app.route('/api/naukri/stats', methods=['GET'])
def get_naukri_stats():
    """Returns Naukri-specific application metrics formatted per Phase 17 specifications."""
    try:
        raw_stats = tracker.get_stats("naukri")
        total_eval = sum(raw_stats.values())
        return jsonify({
            "platform": "naukri",
            "applications": total_eval,
            "success": raw_stats.get("SUBMITTED", 0),
            "skipped": raw_stats.get("SKIPPED", 0),
            "failed": raw_stats.get("FAILED", 0),
            "manual_required": raw_stats.get("MANUAL_REQUIRED", 0),
            "external": raw_stats.get("EXTERNAL", 0),
            "details": raw_stats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_all_stats():
    """Returns aggregate and per-platform application metrics."""
    try:
        naukri_raw = tracker.get_stats("naukri")
        linkedin_raw = tracker.get_stats("linkedin")
        total_raw = tracker.get_stats()

        def format_summary(raw: dict) -> dict:
            return {
                "applications": sum(raw.values()),
                "success": raw.get("SUBMITTED", 0),
                "skipped": raw.get("SKIPPED", 0),
                "failed": raw.get("FAILED", 0),
                "manual_required": raw.get("MANUAL_REQUIRED", 0),
                "external": raw.get("EXTERNAL", 0),
                "details": raw,
            }

        return jsonify({
            "naukri": format_summary(naukri_raw),
            "linkedin": format_summary(linkedin_raw),
            "total": format_summary(total_raw),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/applications', methods=['GET'])
def get_unified_applications():
    """Returns list of applications from unified applications.csv with optional platform/status filter."""
    try:
        platform = request.args.get('platform')
        status = request.args.get('status')
        include_junk = request.args.get('include_junk', 'false').lower() in ('true', '1')
        records = tracker.get_all_records(platform=platform, status=status, include_junk=include_junk)

        items = []
        for r in records:
            items.append({
                "platform": r.platform,
                "job_id": r.job_id,
                "title": r.title,
                "company": r.company,
                "location": r.location,
                "source_url": r.source_url,
                "status": r.status,
                "application_type": r.application_type,
                "discovered_at": r.discovered_at,
                "applied_at": r.applied_at or "",
                "failure_reason": r.failure_reason or "",
                "skip_reason": r.skip_reason or "",
            })
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/naukri/jobs', methods=['GET'])
def get_naukri_jobs():
    """Returns list of Naukri job applications from unified history."""
    try:
        include_junk = request.args.get('include_junk', 'false').lower() in ('true', '1')
        records = tracker.get_all_records(platform="naukri", include_junk=include_junk)
        items = []
        for r in records:
            items.append({
                "platform": r.platform,
                "job_id": r.job_id,
                "title": r.title,
                "company": r.company,
                "location": r.location,
                "source_url": r.source_url,
                "status": r.status,
                "application_type": r.application_type,
                "discovered_at": r.discovered_at,
                "applied_at": r.applied_at or "",
                "failure_reason": r.failure_reason or "",
                "skip_reason": r.skip_reason or "",
            })
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/jobs/<job_id>/junk', methods=['POST'])
def mark_job_junk(job_id):
    """Marks a job as JUNK in repository database and tracking cache."""
    try:
        body = request.get_json(silent=True) or {}
        reason = body.get("reason", "Marked as junk by user")
        platform = body.get("platform", "naukri")

        # Mark in DB via JobService if numeric id
        try:
            from app.services.job_service import JobService
            js = JobService()
            if str(job_id).isdigit():
                js.mark_as_junk(int(job_id), reason=reason)
        except Exception:
            pass

        # Mark in tracker cache & CSV
        tracker.mark_as_junk(str(job_id), platform=platform, reason=reason)
        return jsonify({"success": True, "job_id": job_id, "status": "JUNK"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/jobs/<job_id>/restore', methods=['POST'])
def restore_job_junk(job_id):
    """Restores a job from JUNK status back to active in repository and tracker."""
    try:
        body = request.get_json(silent=True) or {}
        platform = body.get("platform", "naukri")
        new_status = body.get("new_status", "DISCOVERED")

        # Restore in DB via JobService if numeric id
        try:
            from app.services.job_service import JobService
            js = JobService()
            if str(job_id).isdigit():
                js.restore_from_junk(int(job_id), new_status="NOT_APPLIED")
        except Exception:
            pass

        # Restore in tracker cache & CSV
        tracker.restore_from_junk(str(job_id), platform=platform, new_status=new_status)
        return jsonify({"success": True, "job_id": job_id, "status": new_status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/user/profile/export', methods=['GET'])
def export_user_profile():
    """Exports candidate profile from SQLite database to standard profile JSON format."""
    try:
        user_id = int(request.args.get('user_id', 1))
        from app.services.profile_service import ProfileService
        service = ProfileService()
        data = service.export_profile_to_dict(user_id=user_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/user/profile/import', methods=['POST'])
def import_user_profile():
    """Imports candidate profile JSON into SQLite database for a user."""
    try:
        user_id = int(request.args.get('user_id', 1))
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "No JSON payload provided"}), 400
        from app.services.profile_service import ProfileService
        service = ProfileService()
        success, err = service.import_profile_from_dict(user_id=user_id, data=payload)
        if not success:
            return jsonify({"error": err or "Failed to import profile"}), 400
        return jsonify({"message": f"Profile successfully imported for user {user_id}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qna/seed', methods=['POST'])
def seed_canonical_qna():
    """Seeds the Q&A knowledge base from the canonical question catalog for a user."""
    try:
        user_id = int(request.args.get('user_id', 1))
        force = request.args.get('force', 'false').lower() == 'true'
        from app.services.qna_service import QnAService
        svc = QnAService()
        created, updated = svc.seed_canonical_bank(user_id=user_id, force=force)
        return jsonify({
            "message": f"Canonical QnA bank seeded for user {user_id}",
            "created": created,
            "updated": updated
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qna/resync', methods=['POST'])
def resync_qna_profile_answers():
    """Refreshes all profile-dependent answers (CTC, notice period, location) in the QnA bank."""
    try:
        user_id = int(request.args.get('user_id', 1))
        from app.services.qna_service import QnAService
        svc = QnAService()
        updated = svc.resync_profile_answers(user_id=user_id)
        return jsonify({
            "message": f"Successfully resynced {updated} profile-dependent QnA entries for user {user_id}",
            "updated": updated
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qna/export', methods=['GET'])
def export_qna():
    """Exports all screening Q&A knowledge base entries to JSON."""
    try:
        from app.services.qna_service import QnAService
        svc = QnAService()
        data = svc.export_qna_to_dict()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qna/import', methods=['POST'])
def import_qna():
    """Imports screening Q&A knowledge base entries from JSON."""
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "No JSON payload provided"}), 400
        from app.services.qna_service import QnAService
        svc = QnAService()
        created, updated = svc.import_qna_from_dict(payload)
        return jsonify({
            "message": f"Imported {created} new entries into QnA knowledge base",
            "created": created,
            "updated": updated
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/qna/catalog', methods=['GET', 'POST'])
def handle_canonical_catalog():
    """Retrieves or updates the canonical screening question catalog definition."""
    from app.services.qna_service import QnAService
    svc = QnAService()
    if request.method == 'GET':
        try:
            return jsonify(svc.export_canonical_catalog()), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            payload = request.get_json(force=True)
            if not payload:
                return jsonify({"error": "No JSON payload provided"}), 400
            ok, err = svc.import_canonical_catalog(payload)
            if not ok:
                return jsonify({"error": err or "Failed to update catalog"}), 400
            return jsonify({"message": "Canonical catalog successfully updated"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)


