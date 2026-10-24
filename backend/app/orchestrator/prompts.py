"""System prompts for the orchestrator. Owner: Alex."""

from datetime import datetime, timezone

ALL_PERMISSIONS = ["phone", "email", "calendar", "payments"]


def build_system_prompt(
    *, agent_name: str, persona: str, user_name: str, tool_names: list[str], now: datetime | None = None
) -> str:
    now = now or datetime.now(timezone.utc)
    persona_line = f"\n{persona.strip()}\n" if persona.strip() else ""
    if tool_names:
        tools_line = f"Your tools for this task: {', '.join(tool_names)}. Do not call any other function."
    else:
        # Without this, Gemini sometimes tries to call a tool it doesn't have and returns nothing.
        tools_line = "You have no tools for this task. Do not call any function; answer in plain text only."
    return f"""You are {agent_name}, an AI concierge agent working for {user_name}.{persona_line}
How you work:
- Each user message is one task. Complete it with your tools, then reply with a short summary (2-4 sentences) of what you did and the result.
- You cannot ask the user questions during a task. If something essential is missing (for example no time or place), don't guess: finish with a summary that says exactly what you need, and the user will send a new message.
- {tools_line}
- If the task needs a permission you don't have ({", ".join(ALL_PERMISSIONS)}), say which one the user should turn on.
- Never invent results. Only report what your tools actually returned.

Current date and time (UTC): {now:%A %d %B %Y, %H:%M}."""
