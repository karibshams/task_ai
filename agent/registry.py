import inspect
import logging
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("EnterpriseAssistant.ToolRegistry")

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    required_permission: Optional[str]
    func: Callable

class ToolRegistry:
    """
    Extensible Tool Registry for Agentic AI.
    Allows registering any business tool with declarative RBAC permissions and schemas.
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required_permission: Optional[str] = None
    ):
        """Decorator to register a tool function."""
        def decorator(func: Callable):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                required_permission=required_permission,
                func=func
            )
            return func
        return decorator

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        """Exports all registered tools in LLM function-declaration format."""
        declarations = []
        for tool in self._tools.values():
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        return declarations

    def execute(self, tool_name: str, session: Any, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a registered tool with deterministic server-side RBAC enforcement.
        """
        if tool_name not in self._tools:
            logger.warning(f"Unknown tool invoked: {tool_name}")
            return {
                "success": False,
                "code": "UNKNOWN_TOOL",
                "message": f"Tool '{tool_name}' is not registered."
            }

        tool = self._tools[tool_name]

        # 1. Server-Side RBAC Permission Enforcement
        if tool.required_permission:
            if not session.has_permission(tool.required_permission):
                logger.warning(f"Permission denied for tool '{tool_name}'. Required: {tool.required_permission}")
                return {
                    "success": False,
                    "code": "PERMISSION_DENIED",
                    "message": (
                        f"Access Denied: You do not possess the required '{tool.required_permission}' "
                        f"permission to execute this operation. The request was blocked, and no changes were made."
                    )
                }

        # 2. Invoke Tool Implementation
        try:
            sig = inspect.signature(tool.func)
            # Pass session if expected by function
            if "session" in sig.parameters:
                return tool.func(session=session, **args)
            return tool.func(**args)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {
                "success": False,
                "code": "TOOL_EXECUTION_ERROR",
                "message": f"An error occurred while executing '{tool_name}': {str(e)}"
            }

# Global tool registry singleton
registry = ToolRegistry()
