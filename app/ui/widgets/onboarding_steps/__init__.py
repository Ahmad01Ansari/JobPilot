"""
Onboarding Step Widgets Package for JobPilot Setup Wizard (v2.1).
"""

from app.ui.widgets.onboarding_steps.step_welcome import StepWelcomeWidget
from app.ui.widgets.onboarding_steps.step_ai_provider import StepAIProviderWidget
from app.ui.widgets.onboarding_steps.step_resume import StepResumeWidget
from app.ui.widgets.onboarding_steps.step_extraction_progress import StepExtractionProgressWidget
from app.ui.widgets.onboarding_steps.step_profile import StepProfileWidget
from app.ui.widgets.onboarding_steps.step_qna_knowledge import StepQnAKnowledgeWidget
from app.ui.widgets.onboarding_steps.step_preferences import StepPreferencesWidget
from app.ui.widgets.onboarding_steps.step_platforms import StepPlatformsWidget
from app.ui.widgets.onboarding_steps.step_safety import StepSafetyWidget
from app.ui.widgets.onboarding_steps.step_readiness_summary import StepReadinessSummaryWidget

__all__ = [
    "StepWelcomeWidget",
    "StepAIProviderWidget",
    "StepResumeWidget",
    "StepExtractionProgressWidget",
    "StepProfileWidget",
    "StepQnAKnowledgeWidget",
    "StepPreferencesWidget",
    "StepPlatformsWidget",
    "StepSafetyWidget",
    "StepReadinessSummaryWidget",
]
