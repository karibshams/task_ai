import json
import logging
import os
import sys
import urllib.request
import urllib.error
from typing import Optional

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from agent.registry import registry
from agent.security import validate_phone, validate_name
from rag.vector_store import get_vector_store

logger = logging.getLogger("EnterpriseAssistant.Tools")

# ---------------------------------------------------------------------------
# Tool: get_user_profile
# ---------------------------------------------------------------------------
@registry.register(
    name="get_user_profile",
    description="Retrieve the authenticated user's profile information from the business management system. Use when user asks to see, view, or check their profile.",
    parameters={
        "type": "OBJECT",
        "properties": {}
    },
    required_permission="profile.view"
)
def get_user_profile(session) -> dict:
    """Executes GET /profile on the existing business system REST API."""
    token = session.get_token()
    if not token:
        return {
            "success": False,
            "code": "AUTH_ERROR",
            "message": "Authentication failed. Unable to obtain valid session token."
        }

    profile_url = f"{config.API_BASE_URL}/profile"
    req = urllib.request.Request(
        profile_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") is True or data.get("success") is True:
                raw_data = data.get("data", {})
                acc_info = raw_data.get("account_info", {})
                contact_info = raw_data.get("contact_info", {})
                acc_type = raw_data.get("account_type", {})
                company_info = raw_data.get("company_info", {})
                emails = raw_data.get("emails", [])
                primary_email = emails[0].get("email") if emails else session.email

                clean_profile = {
                    "id": acc_info.get("account_id"),
                    "name": acc_info.get("full_name") or f"{acc_info.get('first_name', '')} {acc_info.get('last_name', '')}".strip(),
                    "first_name": acc_info.get("first_name"),
                    "last_name": acc_info.get("last_name"),
                    "email": primary_email,
                    "phone": contact_info.get("cellular_phone_1") or "Not provided",
                    "account_type": acc_type.get("type_display", "Standard User"),
                    "company": company_info.get("limo_company_name", "N/A"),
                    "status": raw_data.get("settings", {}).get("status_label", "ACTIVE")
                }

                # Cache in session
                if session.user_data:
                    session.user_data["cellular_phone_1"] = clean_profile["phone"]
                    session.user_data["first_name"] = clean_profile["first_name"]
                    session.user_data["last_name"] = clean_profile["last_name"]

                return {
                    "success": True,
                    "profile": clean_profile,
                    "message": "Profile retrieved successfully from business system."
                }
            return {
                "success": False,
                "message": data.get("message", "Failed to retrieve profile.")
            }
    except Exception as e:
        logger.error(f"Error fetching profile: {e}", exc_info=True)
        return {
            "success": False,
            "code": "API_ERROR",
            "message": f"Failed to connect to profile service: {str(e)}"
        }

# ---------------------------------------------------------------------------
# Tool: update_user_profile
# ---------------------------------------------------------------------------
@registry.register(
    name="update_user_profile",
    description="Update specific fields of the authenticated user's profile in the business management system. Only call when user has specified which field (such as phone number, first name, or last name) and its new value.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "phone": {
                "type": "STRING",
                "description": "The new mobile or cellular phone number (e.g. '01712345678')."
            },
            "first_name": {
                "type": "STRING",
                "description": "The user's updated first name."
            },
            "last_name": {
                "type": "STRING",
                "description": "The user's updated last name."
            }
        }
    },
    required_permission="profile.update"
)
def update_user_profile(session, phone: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None) -> dict:
    """Executes PUT /profile on the existing business system REST API."""
    # 1. Validate that at least one field is provided
    if not phone and not first_name and not last_name:
        return {
            "success": False,
            "code": "MISSING_INFO",
            "message": "Missing required information: Please specify which profile field you want to update (e.g. phone number, first name, last name) along with the new value."
        }

    # 2. Validate input fields
    api_payload = {}
    if phone:
        valid, cleaned_phone = validate_phone(phone)
        if not valid:
            return {"success": False, "code": "VALIDATION_ERROR", "message": cleaned_phone}
        api_payload["cellular_phone_1"] = cleaned_phone

    if first_name:
        valid, cleaned_fn = validate_name(first_name)
        if not valid:
            return {"success": False, "code": "VALIDATION_ERROR", "message": cleaned_fn}
        api_payload["first_name"] = cleaned_fn

    if last_name:
        valid, cleaned_ln = validate_name(last_name)
        if not valid:
            return {"success": False, "code": "VALIDATION_ERROR", "message": cleaned_ln}
        api_payload["last_name"] = cleaned_ln

    # 3. Execute PUT /profile
    token = session.get_token()
    if not token:
        return {
            "success": False,
            "code": "AUTH_ERROR",
            "message": "Authentication failed. Unable to obtain valid session token."
        }

    profile_url = f"{config.API_BASE_URL}/profile"
    req_body = json.dumps(api_payload).encode("utf-8")
    req = urllib.request.Request(
        profile_url,
        data=req_body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") is True or data.get("success") is True:
                if "cellular_phone_1" in api_payload and session.user_data:
                    session.user_data["cellular_phone_1"] = api_payload["cellular_phone_1"]

                return {
                    "success": True,
                    "message": "Profile updated successfully.",
                    "updated_fields": api_payload,
                    "api_response": data.get("message", "Profile updated.")
                }
            return {
                "success": False,
                "code": "API_REJECTED",
                "message": data.get("message", "Failed to update profile.")
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return {
            "success": False,
            "code": f"HTTP_{e.code}",
            "message": f"API error ({e.code}): {error_body}"
        }
    except Exception as e:
        return {
            "success": False,
            "code": "API_ERROR",
            "message": f"Failed to execute profile update API: {str(e)}"
        }

# ---------------------------------------------------------------------------
# Tool: query_policy_knowledge
# ---------------------------------------------------------------------------
@registry.register(
    name="query_policy_knowledge",
    description="Retrieve relevant sections, pricing rules, limits, and requirements from the official Business System Service Management & Creation Policy (SRV-POL-001). Use this whenever answering questions about service creation, pricing, permissions, or policies.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The search query or topic to look up in the policy document."
            }
        },
        "required": ["query"]
    }
)
def query_policy_knowledge(query: str) -> dict:
    """Retrieves policy clauses and sections from the vector store for a given query."""
    store = get_vector_store()
    results = store.search(query, top_k=3)
    if not results:
        return {
            "found": False,
            "message": "No relevant policy information found in the service policy document.",
            "citations": []
        }

    snippets = []
    citations = []
    for r in results:
        citations.append(r["citation"])
        snippets.append({
            "citation": r["citation"],
            "title": r["title"],
            "section": r["section"],
            "page": r["page"],
            "content": r["content"],
            "similarity_score": round(r["score"], 3)
        })

    return {
        "found": True,
        "results": snippets,
        "citations": citations
    }

# Exported declarations and dispatcher for compatibility
TOOL_DECLARATIONS = registry.get_tool_declarations()

def run_tool(tool_name: str, args: dict, session=None) -> dict:
    """Dispatches tool execution through the extensible ToolRegistry."""
    from agent.session import get_current_session
    sess = session or get_current_session()
    return registry.execute(tool_name, sess, args)
