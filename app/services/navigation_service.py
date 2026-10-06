"""Central Application Navigator managing deep-linking and exact-record navigation lifecycle."""

import logging
from typing import Any, Dict, Optional

from app.services.search.search_result import NavigationAction, NavigationRequest

logger = logging.getLogger(__name__)


class AppNavigator:
    """Coordinates deep-link navigation between global search and views.

    Guarantees that exact navigation state survives view activation and refresh().
    """

    def __init__(self, main_window: Any) -> None:
        self.main_window = main_window

    def navigate(self, request: NavigationRequest) -> bool:
        """Executes a centralized navigation request.

        Args:
            request: NavigationRequest with target route, entity_type, entity_id, and action mode.

        Returns:
            bool: True if navigation was successfully routed, False otherwise.
        """
        route = request.route
        if not route or not hasattr(self.main_window, "view_instances"):
            logger.warning("Navigation failed: invalid route '%s' or view instances missing", route)
            return False

        view = self.main_window.view_instances.get(route)
        if not view:
            logger.warning("Destination view '%s' not registered in MainWindow", route)
            return False

        current_route = None
        if hasattr(self.main_window, "state"):
            state = self.main_window.state
            if isinstance(getattr(state, "current_page", None), str):
                current_route = state.current_page
            elif isinstance(getattr(state, "current_page_id", None), str):
                current_route = state.current_page_id
        is_already_active = (current_route == route)

        try:
            if is_already_active:
                # View is already displayed; dispatch request immediately
                if hasattr(view, "handle_navigation_request"):
                    view.handle_navigation_request(request)
                else:
                    self._legacy_fallback_dispatch(view, request)
            else:
                # View is not currently active; arm it before triggering view switch
                if hasattr(view, "arm_navigation_request"):
                    view.arm_navigation_request(request)

                # Switch active view in MainWindow (which invokes view.refresh())
                self.main_window.navigate_to(route)

                # If view did not auto-consume during refresh, ensure it executes now
                if hasattr(view, "handle_navigation_request") and getattr(view, "_pending_navigation_request", None):
                    view.handle_navigation_request(request)

            return True

        except Exception as e:
            logger.exception("Error executing navigation request %s: %s", request, e)
            self._notify_error(f"Failed to navigate to {request.entity_type} #{request.entity_id}: {e}")
            return False

    def _legacy_fallback_dispatch(self, view: Any, request: NavigationRequest) -> None:
        """Fallback for views that haven't yet implemented handle_navigation_request."""
        entity_id = request.entity_id
        if request.route == "jobs" and hasattr(view, "inspect_job_by_id"):
            view.inspect_job_by_id(entity_id)
        elif request.route == "applications" and hasattr(view, "inspect_application_by_id"):
            view.inspect_application_by_id(entity_id)
        elif request.route == "outreach" and hasattr(view, "select_conversation"):
            view.select_conversation(entity_id)
        elif request.route == "interviews" and hasattr(view, "inspect_interview_by_id"):
            view.inspect_interview_by_id(entity_id)
        elif request.route == "followups" and hasattr(view, "highlight_follow_up"):
            view.highlight_follow_up(entity_id)

    def _notify_error(self, message: str) -> None:
        """Displays error toast via MainWindow notification state."""
        if hasattr(self.main_window, "state") and hasattr(self.main_window.state, "notify"):
            self.main_window.state.notify("danger", message)
