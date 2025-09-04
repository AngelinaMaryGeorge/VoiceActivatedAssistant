from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import datetime
import json
import os
from dotenv import load_dotenv
from flask import send_from_directory
import re

# --- Configuration ---
# Load environment variables from the .env file.
# Make sure to create a .env file in the same directory as this script
# with your API keys
# OPENWEATHER_API_KEY="your_api_key_here"
# GUARDIAN_API_KEY="your_api_key_here"
load_dotenv()

# Get API keys and other configuration from environment variables.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY")
WEATHER_LOCATION = "New Delhi"


# --- Initialization ---
app = Flask(__name__)
# Enable CORS to allow the frontend webpage to make requests to this server.
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'frontend.html')

# This list will store reminders. In a real-world app, this would be a database
# like Firebase Firestore to ensure they are persistent.
reminders = []

# --- Core Functions (now return JSON) ---

def get_city_coords(city_name):
    """
    Uses the OpenWeatherMap Geocoding API to get geographical coordinates for a city name.
    """
    if not OPENWEATHER_API_KEY:
        return None
    
    base_url = "https://api.openweathermap.org/geo/1.0/direct?"
    complete_url = f"{base_url}q={city_name}&limit=1&appid={OPENWEATHER_API_KEY}"
    
    try:
        response = requests.get(complete_url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        if data and len(data) > 0:
            location_data = data[0]
            lat = location_data.get("lat")
            lon = location_data.get("lon")
            return (lat, lon)
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching city coordinates: {e}")
        return None

def get_weather_data(location=None):
    """
    Fetches the current weather for a specified or default location and returns a dict.
    """
    if not OPENWEATHER_API_KEY:
        return {"text": "Please set your OpenWeatherMap API key."}
    
    location_to_use = location if location else WEATHER_LOCATION
    
    coords = get_city_coords(location_to_use)

    if coords:
        lat, lon = coords
        base_url = "https://api.openweathermap.org/data/2.5/weather?"
        complete_url = f"{base_url}lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    else:
        # Fallback to city name search if geocoding fails
        base_url = "https://api.openweathermap.org/data/2.5/weather?"
        complete_url = f"{base_url}q={location_to_use}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(complete_url)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        if data.get("cod") != "404":
            main_data = data["main"]
            weather_data = data["weather"][0]
            temperature = main_data.get("temp")
            humidity = main_data.get("humidity", "not available")
            pressure = main_data.get("pressure", "not available")
            weather_description = weather_data.get("description")
            
            response_text = f"The temperature in {location_to_use} is {temperature:.1f} degrees Celsius, with {weather_description}. The humidity is {humidity} percent, and the atmospheric pressure is {pressure} hectopascals."
            return {
                "text": response_text,
                "location": location_to_use,
                "temperature": f"{temperature:.1f} °C",
                "humidity": f"{humidity}%",
                "pressure": f"{pressure} hPa",
                "description": weather_description
            }
        else:
            return {"text": f"I couldn't find the weather for {location_to_use}."}
    except requests.exceptions.RequestException as e:
        return {"text": f"Sorry, I had trouble getting the weather. The error was: {e}"}


def get_news_data(query=None):
    """
    Fetches the top news headlines for a given query and returns a dict.
    """
    if not GUARDIAN_API_KEY:
        return {"text": "Please set your Guardian API key.", "articles": []}
    
    base_url = "https://content.guardianapis.com/search?"
    one_day_ago = datetime.date.today() - datetime.timedelta(days=1)
    from_date_param = f"&from-date={one_day_ago.isoformat()}"
    
    complete_url = f"{base_url}{from_date_param}&order-by=newest&page-size=5&api-key={GUARDIAN_API_KEY}"

    if query:
        common_tags = ["politics", "technology", "sports", "science", "business"]
        
        if query in common_tags:
            complete_url += f"&q={query}&tag={query}/{query}"
            intro_text = f"Getting the latest news about {query} from yesterday from The Guardian."
        else:
            complete_url += f"&q={query}"
            intro_text = f"Getting the latest news about {query} from yesterday from The Guardian."
    else:
        intro_text = "Here are the top headlines from yesterday from The Guardian:"
    
    try:
        response = requests.get(complete_url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("response", {}).get("status") == "ok" and data.get("response", {}).get("results"):
            articles = data["response"]["results"]
            if not articles:
                return {"text": "I couldn't find any news headlines for that topic from yesterday.", "articles": []}
            
            urls = [{"title": article['webTitle'], "url": article['webUrl']} for article in articles]
            headlines_text = ". ".join([f"Headline number {i + 1}: {article['webTitle']}" for i, article in enumerate(articles)])
            
            return {
                "text": f"{intro_text} {headlines_text}. Would you like me to provide the URLs to see the full articles?",
                "articles": urls
            }
        else:
            return {"text": "I couldn't fetch any news headlines at the moment.", "articles": []}
    except requests.exceptions.RequestException as e:
        return {"text": f"Sorry, I had trouble getting the news. The error was: {e}", "articles": []}

def set_reminder_data(reminder_text, time_str):
    """
    Parses reminder time and text and returns a dict.
    """
    try:
        # Check for seconds
        if "seconds" in time_str:
            seconds = int(time_str.split(" ")[0])
            reminder_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            reminder_data = {"time": reminder_time.isoformat(), "text": reminder_text}
            reminders.append(reminder_data)
            return {"text": f"Okay, I will remind you to '{reminder_text}' in {seconds} seconds.", "reminder": reminder_data}
        # Check for minutes
        elif "minutes" in time_str:
            minutes = int(time_str.split(" ")[0])
            reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            reminder_data = {"time": reminder_time.isoformat(), "text": reminder_text}
            reminders.append(reminder_data)
            return {"text": f"Okay, I will remind you to '{reminder_text}' in {minutes} minutes.", "reminder": reminder_data}
        else:
            return {"text": "I can only set reminders in seconds or minutes for now. Please try again."}
    except (ValueError, IndexError):
        return {"text": "Sorry, I couldn't understand the time. Please specify a number followed by 'seconds' or 'minutes'."}


# --- API Endpoint ---
@app.route('/process_command', methods=['POST'])
def process_command():
    """
    API endpoint to receive and process voice commands.
    """
    try:
        data = request.json
        command = data.get("command", "").lower()
        print(f"Received command: {command}")
        
        response_data = {"text": "I'm sorry, I don't understand that command yet. Please try again.", "type": "error"}

        # Check for command keywords
        if any(keyword in command for keyword in ["time", "hour", "clock", "o'clock"]):
            now = datetime.datetime.now().strftime("%I:%M %p")
            response_data = {"text": f"The current time is {now}", "type": "time"}

        elif any(keyword in command for keyword in ["weather", "climate", "forecast", "meteorology", "temperature", "cloud cover", "windspeed", "humidity", "pressure"]):
            location_to_check = None
            if "weather in" in command or "weather at" in command:
                location_keyword = "weather in" if "weather in" in command else "weather at"
                location_start_index = command.find(location_keyword) + len(location_keyword)
                location_to_check = command[location_start_index:].strip()
            
            weather_response = get_weather_data(location=location_to_check)
            response_data = {"type": "weather", **weather_response}
        
        elif "news" in command:
            query = None
            trigger_words = ["on", "about", "relating to", "for"]
            for word in trigger_words:
                if f" {word} " in command:
                    try:
                        query = command.split(word, 1)[1].strip()
                        break
                    except IndexError:
                        pass
            
            news_response = get_news_data(query=query)
            response_data = {"type": "news", **news_response}

        elif any(keyword in command for keyword in ["reminder", "remind me", "set reminder"]):
            # Use regex to find a time pattern (e.g., "5 minutes" or "10 seconds")
            match = re.search(r'(\d+)\s*(seconds?|minutes?)', command)
            if match:
                time_str = match.group(0)
                # Split the command at the time string to get the reminder message
                reminder_text_part = command.split(time_str, 1)[1].strip()

                # Find the beginning of the message, if "to" is present.
                if " to " in reminder_text_part:
                    reminder_text = reminder_text_part.split(" to ", 1)[1].strip()
                else:
                    reminder_text = reminder_text_part
                
                if reminder_text:
                    reminder_response = set_reminder_data(reminder_text, time_str)
                    response_data = {"type": "reminder_set", **reminder_response}
                else:
                    response_data = {"text": "I found a time, but couldn't find a reminder message. Please use a phrase like 'remind me in 5 minutes to call mom.'", "type": "error"}
            else:
                response_data = {"text": "To set a reminder, please use a phrase like, 'set a reminder to take out the trash in 5 minutes'.", "type": "error"}

        elif any(word in command for word in ["yes", "would like", "i'd like that", "affirmative", "confirmative", "yep", "yeah", "please do", "sure", "positive", "do it"]):
            response_data = {"text": "Okay, displaying the links now.", "type": "news_confirmation"}

        elif any(word in command for word in ["exit", "goodbye", "bye", "see you later", "tata", "see ya", "shareenna", "alvida", "adios", "ciao", "au revoir", "sayonara", "pootte"]):
            response_data = {"text": "Goodbye! Have a great day.", "type": "goodbye"}
        
        # Check for reminders periodically (this is a simple, non-blocking check)
        # This will only work if the user is actively using the assistant and sends a command.
        current_time = datetime.datetime.now()
        reminders_to_remove = []
        for reminder in reminders:
            if current_time >= datetime.datetime.fromisoformat(reminder["time"]):
                response_data = {"text": f"Reminder: {reminder['text']}", "type": "reminder_alert"}
                reminders_to_remove.append(reminder)
        
        for reminder in reminders_to_remove:
            reminders.remove(reminder)
        
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"text": f"An error occurred: {e}", "type": "error"}), 500

if __name__ == "__main__":
    app.run(debug=True)
