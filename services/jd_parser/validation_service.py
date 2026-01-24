"""JD parsing validation service."""

from typing import Dict, Any, Optional
from packages.schemas.jd_schema import ParsedJD
from packages.common.logging import get_logger

logger = get_logger(__name__)


class JDValidationService:
    """Validate parsed JD data."""
    
    @staticmethod
    def validate(parsed_data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[ParsedJD]]:
        """Validate parsed JD data.
        
        Args:
            parsed_data: Parsed JD data dictionary
        
        Returns:
            Tuple of (is_valid, error_message, parsed_jd)
        """
        try:
            parsed_jd = ParsedJD(**parsed_data)
            return True, None, parsed_jd
        except Exception as e:
            error_msg = f"Validation failed: {str(e)}"
            logger.warning(error_msg)
            return False, error_msg, None
    
    @staticmethod
    def validate_required_fields(parsed_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Check if required fields are present.
        
        Args:
            parsed_data: Parsed JD data dictionary
        
        Returns:
            Tuple of (is_valid, missing_fields)
        """
        required_fields = ["role"]
        missing = [field for field in required_fields if not parsed_data.get(field)]
        
        return len(missing) == 0, missing
