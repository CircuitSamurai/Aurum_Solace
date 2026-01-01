from fastapi import FastAPI
from pydantic import BaseModel
from . import storage


app = FastAPI(title="Aurum_Solace Server")

@app.on_event("startup")
def on_startup():
    storage.init_db()

# -------------------------
# Data model for mood input
# -------------------------
class MoodCheckIn(BaseModel):
    mood: str        # "low", "neutral", "good"
    energy: str      # "low", "medium", "high"
    focus: str       # "drifting", "ok", "locked-in"




class ActionLog(BaseModel):
    action: str
    success: bool = True





# -------------------------
# suggestion logic
# -------------------------
def suggest_action(mood: str, energy: str, focus: str) -> str:
    mood = mood.lower()
    energy = energy.lower()
    focus = focus.lower()

    if mood == "low" and energy == "low":
        return "You seem low today — pick the smallest act of self-care you can manage: a glass of water, a stretch, or one deep breath."

    if mood == "low" and energy in ("medium", "high"):
        return "Energy is present even if mood is low — try one tiny 5-minute task to regain control."

    if mood == "neutral" and focus == "drifting":
        return "You're steady but scattered — choose a single priority and work on it for 10 focused minutes."

    if mood == "good" and energy in ("medium", "high"):
        return "Great conditions today — move something meaningful forward with 20 minutes of deep focus."

    return "Start small — what is one simple action Future You would thank you for?"


# -------------------------
# existing test endpoint
# -------------------------
@app.get("/ping")
def ping():
    return {"message": "Brain online and listening."}


# -------------------------
# NEW mood check-in endpoint
# -------------------------
@app.post("/checkin/mood", description="Mood check-in")
def checkin_mood(data: MoodCheckIn):
    entry = storage.insert_mood(
        mood=data.mood,
        energy=data.energy,
        focus=data.focus, 
    )

    suggestion = suggest_action(data.mood, data.energy, data.focus)

    return {
        "status": "stored",
        "entry": entry,
        "suggestion": suggestion
    }

@app.post("/action/log")
def log_action(data: ActionLog):
    #Save to data base (storage.py)
    entry = storage.insert_action( 
        action=data.action,
        success=data.success
    )


    return {
        "status": "stored",
        "entry": entry
    }

@app.get("/summary", description="Summary of Logs")
def summary():
    return storage.get_summary()

@app.get("/streak/actions", description="Current action streak in days")
def action_streak():
    return storage.get_action_streak()


@app.get("/history/mood", description="Recent mood check-ins (newest first)")
def mood_history(limit: int = 20):
    return storage.get_mood_history(limit=limit)

@app.get("/history/actions", description="Recent action logs (newest first)")
def action_history(limit: int = 20):
    return storage.get_action_history(limit=limit)

@app.get("/coach", description="Get a suggested next step based on your latest mood check-in.")
def coach():
    # Get the most recent mood entry from the database
    history = storage.get_mood_history(limit=1)

    if not history:
        # No mood data collected yet - return a gentle message
        return {
            "message": "No mood check-ins found yet. Do a quick check-in first so I can suggest something.",
            "suggestion": None,
        }

    last = history[0]

    # Use correct keys from the DB rows
    mood = last.get("mood", "neutral")
    energy = last.get("energy", "medium")
    focus = last.get("focus", "ok")

    # 2) Base suggestion from mood
    base_suggestion = suggest_action(
        mood=mood,
        energy=energy,
        focus=focus,
    )

    # 3) Pull current streak
    streak_info = getattr(storage, "get_action_streak", None)
    if callable(streak_info):
        streak_data = storage.get_action_streak()
    else:
        streak_data = {"streak_days": 0, "last_action_date": None}

    streak_days = streak_data.get("streak_days", 0)

    # 4) Add streak-aware nuance
    if streak_days >= 3:
        extra = f" You're on a {streak_days}-day streak. Protect it with one small action today."
    elif streak_days == 1 or streak_days == 2:
        extra = f" Good start — you're at {streak_days} day of action. Let's keep it going."
    else:
        extra = " Let's just focus on winning today with one meaningful action."

    suggestion = f"{base_suggestion} {extra}"

    return {
        "based_on": {
            "timestamp": last.get("timestamp"),
            "mood": mood,
            "energy": energy,
            "focus": focus,
        },
        "streak": streak_data,
        "suggestion": suggestion,
    }
