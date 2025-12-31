from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
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