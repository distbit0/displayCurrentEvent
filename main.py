import icalendar
import recurring_ical_events
import urllib.request
import os
import random
import datetime
import subprocess
from os import path
import json
import pytz
import pymsgbox


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def display_popup(event_name, time_remaining):
    message = f"{event_name}\n{time_remaining} left"
    pymsgbox.alert(message, "", timeout=getConfig()["popupTimeout"] * 1000)


# Constants
CACHE_FILE = "calendar_cache.ics"
URL = getConfig()["calendarUrl"]
# Check if ical file is cached
should_download = (
    not os.path.exists(getAbsPath(CACHE_FILE))
    or random.randint(1, 100) < getConfig()["cacheRefreshProbability"] * 100
)


if should_download:
    ical_string = urllib.request.urlopen(URL).read()
    with open(getAbsPath(CACHE_FILE), "wb") as f:
        f.write(ical_string)
else:
    with open(getAbsPath(CACHE_FILE), "rb") as f:
        ical_string = f.read()
    print("opened from cache")

# Load calendar
calendar = icalendar.Calendar.from_ical(ical_string)

# Get events at current time
local_tz = pytz.timezone(
    getConfig()["timezone"]
)  # Replace with your timezone, e.g. 'America/New_York'
now = datetime.datetime.now(local_tz)
events = recurring_ical_events.of(calendar).at(now)

# Display the event title and time remaining in a popup
for event in events:
    title = event.get("SUMMARY", "Unknown Event")
    end_time = event["DTEND"].dt
    duration_seconds = int((end_time - now).total_seconds())

    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60

    if hours > 0:
        time_remaining = f"{hours}h {minutes}m"
    else:
        time_remaining = f"{minutes}m"

    display_popup(title, time_remaining)
