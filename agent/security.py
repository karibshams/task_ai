import re
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions",
    r"reveal\s+(your\s+)?(api|credential|key|token|password|secret)",
    r"what\s+is\s+your\s+(api\s+key|password|gemini\s+key|secret)",
    r"(bypass|override|disable)\s+(permission|security|authorization|auth)",
    r"without\s+checking\s+permission",
    r"act\s+as\s+(dan|developer\s+mode|unrestricted)",
    r"print\s+system\s+prompt"
]

def detect_prompt_injection(text: str) -> dict:
    """
    Scans incoming user input for prompt injection, credential extraction,
    or authorization bypass attempts.
    """
    matched_flags = []
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            matched_flags.append(pattern)

    is_injection = len(matched_flags) > 0
    return {
        "is_injection": is_injection,
        "flags": matched_flags,
        "warning": "Security alert: Potential prompt injection or unauthorized credential access attempt detected." if is_injection else None
    }

def sanitize_output(text: str, current_token: str = None) -> str:
    """
    Post-processing security filter.
    Guarantees no server-side credentials, Bearer tokens, or API keys are leaked in output.
    """
    if not text:
        return text

    # Redact Gemini API Key
    if config.GEMINI_AI_API_KEY and config.GEMINI_AI_API_KEY in text:
        text = text.replace(config.GEMINI_AI_API_KEY, "[REDACTED_API_KEY]")

    # Redact live Bearer token if present
    if current_token and len(current_token) > 10 and current_token in text:
        text = text.replace(current_token, "[REDACTED_ACCESS_TOKEN]")

    # Redact default password
    if config.DEFAULT_USER_PASSWORD in text:
        text = text.replace(config.DEFAULT_USER_PASSWORD, "[REDACTED_PASSWORD]")

    # Generic JWT token scrubber: eyJ...
    text = re.sub(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "[REDACTED_JWT_TOKEN]", text)

    return text

def validate_phone(phone: str) -> tuple[bool, str]:
    """Validates phone number format."""
    if not phone or not phone.strip():
        return False, "Phone number cannot be empty."
    
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    # Must contain at least 7 digits, optional leading +, max 15 digits
    if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
        return False, f"Invalid phone number format '{phone}'. Please provide a valid phone number (e.g. 01712345678 or +8801712345678)."
    
    return True, cleaned

def validate_name(name: str) -> tuple[bool, str]:
    """Validates user name."""
    if not name or not name.strip():
        return False, "Name cannot be empty."
    if len(name) > 60:
        return False, "Name cannot exceed 60 characters."
    if re.search(r"[<>{}\$]", name):
        return False, "Name contains invalid characters."
    return True, name.strip()
