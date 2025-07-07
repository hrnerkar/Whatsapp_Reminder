from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import threading
import time
import dateparser
import schedule
from twilio.rest import Client
import re
import os

# Set timezone
os.environ['TZ'] = 'Asia/Kolkata'
try:
    time.tzset()
except AttributeError:
    pass  # Ignore on Windows

app = Flask(__name__)

# Store reminders in memory
reminders = []

# Twilio credentials
account_sid = 'AC1d5f9abefa2758149474e435bf79c970'
auth_token = 'e722f2e96fb176e2c3694888fa698324'
twilio_client = Client(account_sid, auth_token)

# Twilio sandbox WhatsApp number
from_number = 'whatsapp:+14155238886'

# Function to extract time from message
def extract_time_text(message):
    patterns = [
        r"(tomorrow\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm))",
        r"(today\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm))",
        r"(\d{1,2}(:\d{2})?\s*(am|pm))"
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

# Create confirmation message
def generate_confirmation(task, time_obj):
    time_str = time_obj.strftime("%A, %d %B %Y at %I:%M %p")
    return f"Noted! I’ll remind you to '{task}' on {time_str}."

# WhatsApp webhook route
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    sender_number = request.values.get("From", "")
    print(f"📩 Received message from {sender_number}: {incoming_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    time_text = extract_time_text(incoming_msg)
    print(f"🕵️ Extracted time part: {time_text if time_text else 'None'}")

    parsed_time = None
    if time_text:
        parsed_time = dateparser.parse(
            time_text,
            settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': datetime.now(),
                'TIMEZONE': 'Asia/Kolkata',
                'RETURN_AS_TIMEZONE_AWARE': False
            }
        )

    if parsed_time:
        parsed_time = parsed_time.replace(second=0, microsecond=0)
        task_text = incoming_msg.replace(time_text, "").strip().rstrip(".,;:") or "do the task"

        # Avoid duplicate
        for r in reminders:
            if r[0] == parsed_time and r[2] == sender_number:
                msg.body("You already have a reminder at that time.")
                return str(resp)

        reminders.append((parsed_time, task_text, sender_number))
        confirmation = generate_confirmation(task_text, parsed_time)
        msg.body("✅ " + confirmation)
        print(f"⏰ Scheduled reminder for {parsed_time} with task: {task_text}")
    else:
        msg.body("⚠️ I couldn’t understand the time. Try something like: 'Remind me to call tomorrow at 3 PM'")
        print("❌ Failed to parse time.")

    return str(resp)

# Scheduler
def check_reminders():
    now = datetime.now().replace(second=0, microsecond=0)
    print(f"🕓 Checking reminders at: {now.strftime('%Y-%m-%d %H:%M')}")

    for rem_time, message, number in list(reminders):
        if rem_time == now:
            try:
                twilio_client.messages.create(
                    body=f"🔔 Reminder: {message}",
                    from_=from_number,
                    to="whatsapp:+917522946205"
                )
                print(f"✅ Sent reminder to {number}: {message}")
                reminders.remove((rem_time, message, number))
            except Exception as e:
                print(f"❌ Error sending message: {e}")

# Run scheduler in background
def run_scheduler():
    schedule.every(15).seconds.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start Flask server
if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("🚀 Flask app running on http://localhost:5000")
    app.run(port=5000)
