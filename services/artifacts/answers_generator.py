"""Short answers generator for screening questions."""

from typing import List, Dict, Any
from packages.common.logging import get_logger

logger = get_logger(__name__)


class AnswersGenerator:
    """Generate answers for common screening questions."""

    COMMON_QUESTIONS = {
        "years_of_experience": "How many years of experience do you have?",
        "availability": "When are you available to start?",
        "salary_expectation": "What are your salary expectations?",
        "visa_status": "Do you require visa sponsorship?",
        "location": "Are you willing to relocate?",
        "remote": "Are you open to remote work?",
    }

    def generate_answer(self, question: str, user_data: Dict[str, Any]) -> str:
        """Generate answer for a question.

        Args:
            question: Question text
            user_data: User data (preferences, profile, etc.)

        Returns:
            Answer text
        """
        question_lower = question.lower()

        # Years of experience
        if "experience" in question_lower or "years" in question_lower:
            years = user_data.get("years_of_experience", "several")
            return f"I have {years} years of professional experience in software development."

        # Availability
        if "available" in question_lower or "start" in question_lower:
            return (
                "I am available to start within 2-4 weeks, depending on notice period requirements."
            )

        # Salary
        if "salary" in question_lower or "compensation" in question_lower:
            min_salary = user_data.get("salary_min_usd")
            if min_salary:
                return f"My salary expectations are in the range of ${min_salary:,}+, depending on the total compensation package."
            return "I'm open to discussing compensation based on the role and total package."

        # Visa
        if "visa" in question_lower or "sponsorship" in question_lower:
            visa_status = user_data.get("visa_status", "")
            if "h1b" in visa_status.lower():
                return (
                    "I currently hold H1B status and would require sponsorship for a new employer."
                )
            elif "citizen" in visa_status.lower() or "green card" in visa_status.lower():
                return "I am authorized to work in the US and do not require visa sponsorship."
            return "I am authorized to work in the US."

        # Location/Remote
        if "remote" in question_lower:
            loc_prefs = user_data.get("location_preferences", {})
            if isinstance(loc_prefs, dict) and loc_prefs.get("remote_only"):
                return "Yes, I am open to and prefer remote work opportunities."
            return "I am open to remote, hybrid, or onsite work depending on the role."

        if "relocate" in question_lower:
            return "I am open to discussing relocation for the right opportunity."

        # Default answer
        return "I would be happy to discuss this further during our conversation."
