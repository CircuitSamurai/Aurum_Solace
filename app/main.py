from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from . import storage
from typing import Optional


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




class MoodTextIn(BaseModel):
    text: str # free-form text about how the user feels




class FeedbackIn(BaseModel):
    helped: bool
    note: Optional[str] = None



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



def infer_state_from_text(text: str):
    """
    Very simple rule-based classifier for now.
    Later, this is where a real LLM or model call will live.
    """
    t = text.lower()

    # Default values
    mood = "neutral"
    energy = "medium"
    focus = "ok"
    confidence = 0.4  # arbitrary baseline

    # --- Mood keywords ---
    if any(word in t for word in ["sad", "down", "depressed", "empty", "tired of", "overwhelmed"]):
        mood = "low"
        confidence = 0.7
    elif any(word in t for word in ["good", "great", "excited", "happy", "pumped", "optimistic"]):
        mood = "good"
        confidence = 0.7

    # --- Energy keywords ---
    if any(word in t for word in ["exhausted", "drained", "tired", "low energy", "wiped"]):
        energy = "low"
    elif any(word in t for word in ["wired", "energized", "hyped", "ready to go", "full of energy"]):
        energy = "high"

    # --- Focus keywords ---
    if any(word in t for word in ["scattered", "can't focus", "distracted", "all over the place"]):
        focus = "drifting"
    elif any(word in t for word in ["locked in", "dialed in", "focused", "in the zone"]):
        focus = "locked-in"

    return {
        "mood": mood,
        "energy": energy,
        "focus": focus,
        "confidence": confidence,
    }



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

@app.get("/history/actuations", description="Recent actuation decisions (newest first)")
def actuation_history(limit: int = 20):
    return storage.get_actuation_history(limit=limit)


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


@app.post("/infer/mood", description="Infer mood, energy, and focus from free-form text.")
def infer_mood(data: MoodTextIn):
    result = infer_state_from_text(data.text)

    return {
        "input_text": data.text,
        "mood": result["mood"],
        "energy": result["energy"],
        "focus": result["focus"],
        "confidence": result["confidence"],
    }


@app.post("/checkin/text", description="Auto-checkin: infer mood/energy/focus from text, store it, and return coaching.")
def checkin_text(data: MoodTextIn):
    # 1) Infer state from text
    inferred = infer_state_from_text(data.text)

    mood = inferred["mood"]
    energy = inferred["energy"]
    focus = inferred["focus"]

    # 2) Store in DB using your existing storage function
    entry = storage.insert_mood(
        mood=mood,
        energy=energy,
        focus=focus,
    )

    # 3) Generate coaching suggestion
    base_suggestion = suggest_action(mood=mood, energy=energy, focus=focus)

    # 4) (Optional) streak-aware add-on
    streak_info = getattr(storage, "get_action_streak", None)
    if callable(streak_info):
        streak_data = storage.get_action_streak()
    else:
        streak_data = {"streak_days": 0, "last_action_date": None}

    streak_days = streak_data.get("streak_days", 0)

    if streak_days >= 3:
        extra = f" You're on a {streak_days}-day streak. Protect it with one small action today."
    elif streak_days in (1, 2):
        extra = f" Good start — you're at {streak_days} day of action. Let's keep it going."
    else:
        extra = " Let's just focus on winning today with one meaningful action."

    suggestion = f"{base_suggestion} {extra}"

    return {
        "status": "stored",
        "input_text": data.text,
        "inferred": {
            "mood": mood,
            "energy": energy,
            "focus": focus,
            "confidence": inferred.get("confidence", 0.0),
        },
        "entry": entry,
        "streak": streak_data,
        "suggestion": suggestion,
    }


@app.get("/status", description="Server heartbeat + latest state snapshot for devices.")
def status():
    latest_mood = storage.get_latest_mood()
    counts = storage.get_summary()

    streak_info = getattr(storage, "get_action_streak", None)
    if callable(streak_info):
        streak = storage.get_action_streak()
    else:
        streak = {"streak_days": 0, "last_action_date": None}

    return {
        "server": "online",
        "utc_time": datetime.utcnow().isoformat(),
        "latest_mood": latest_mood,
        "streak": streak,
        "counts": counts,
    }


@app.get("/actuate", description="Return recommended actions for lights/speaker/robot based on latest state.")
def actuate(device: Optional[str] = None):
    # 1) Get latest mood state (fallbacks if none yet)
    history = storage.get_mood_history(limit=1)
    last = history[0] if history else None

    mood = (last.get("mood") if last else "neutral")
    energy = (last.get("energy") if last else "medium")
    focus = (last.get("focus") if last else "ok")

    # 2) Streak (optional)
    streak_info = getattr(storage, "get_action_streak", None)
    if callable(streak_info):
        streak = storage.get_action_streak()
    else:
        streak = {"streak_days": 0, "last_action_date": None}
    streak_days = streak.get("streak_days", 0)

    # 3) Ground State
    lights = {
        "scene": "neutral",
        "color_temp_k": 2700,
        "brightness": 45,
        "effect": "steady",
        "duration_s": 1800,
    }

    speaker = {
        "soundscape": "silence",
        "volume": 20,
        "fade_in_s": 5,
        "duration_s": 0,
    }

    robot = {
        "script": "idle_presence",
        "tone": "calm",
        "line": None,
        "task": None,
        "timer_s": None,
    }

    # 4) Rules (simple now, ML later)
    if mood == "low" and energy == "low":
        lights.update({
            "scene": "ember",
            "color_temp_k": 2200,
            "brightness": 20,
            "effect": "breathe",
            "duration_s": 900,
        })
        speaker.update({
            "soundscape": "rain_soft",
            "volume": 22,
            "fade_in_s": 8,
            "duration_s": 600,
        })
        robot.update({
            "script": "micro_step_support",
            "tone": "soft",
            "line": "We go small. Stand up. Drink water. One minute.",
            "task": "drink_water",
            "timer_s": 60,
        })


    # 5) Streak nuance
    if streak_days >= 3:
        robot["script"] = f"{robot['script']}_protect_streak"

    storage.insert_actuation(
        mood=mood,
        energy=energy,
        focus=focus,
        streak_days=streak_days,
        lights=lights,
        speaker=speaker,
        robot=robot,
        requested_device=device,
    )


    response = {
        "version": "0.1.0",
        "node": "aurum-brain-1",
        "based_on": {
            "timestamp": (last.get("timestamp") if last else None),
            "mood": mood,
            "energy": energy,
            "focus": focus,
            "streak_days": streak_days,
        },
        "commands": {
            "lights": lights,
            "speaker": speaker,
            "robot": robot,
        },
    }

    if device:
        d = device.lower().strip()
        if d in response["commands"]:
            response["commands"] = {d: response["commands"][d]}
        else:
            return {
                "error": f"Unknown device '{device}'. Use lights, speaker, or robot."
            }

    return response

@app.post("/feedback", description="Log whether the last actuation helped.")
def feedback(data: FeedbackIn):
    return storage.insert_feedback(helped=data.helped, note=data.note)


@app.get("/history/feedback", description="Recent feedback (newest first).")
def feedback_history(limit: int = 20):
    return storage.get_feedback_history(limit=limit)
