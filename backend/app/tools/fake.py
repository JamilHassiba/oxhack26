"""Phase 0 fake tool to prove the Gemini function-calling loop. Not exposed to real agents."""

from app.tools.base import Tool

FULLY_BOOKED = {"18:00", "19:00"}


async def check_availability(restaurant: str, party_size: int, time: str) -> dict:
    if party_size > 8:
        return {"available": False, "reason": "Parties over 8 must call the manager."}
    if time in FULLY_BOOKED:
        return {"available": False, "alternatives": ["17:30", "20:30"]}
    return {"available": True, "restaurant": restaurant, "party_size": party_size, "time": time}


check_availability_tool = Tool(
    name="check_availability",
    description="Check whether a restaurant has a free table for a party at a given time.",
    parameters={
        "type": "object",
        "properties": {
            "restaurant": {"type": "string", "description": "Restaurant name."},
            "party_size": {"type": "integer", "description": "Number of people."},
            "time": {"type": "string", "description": "24h time, HH:MM."},
        },
        "required": ["restaurant", "party_size", "time"],
    },
    handler=check_availability,
)
