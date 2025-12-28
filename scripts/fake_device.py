import requests

BASE_URL = "http://127.0.0.1:8000"

def send_mood(mood, energy, focus):
    payload = {"mood": mood, "energy": energy, "focus": focus}
    r = requests.post(f"{BASE_URL}/checkin/mood", json=payload)
    print(r.json())

if __name__ == "__main__":
    send_mood("low", "low", "drifting")