import icalendar
import recurring_ical_events
import urllib.request
import os
import random
import datetime
import subprocess
from os import path
import json


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def display_popup(event_name):
    command = [
        "zenity",
        "--info",
        "--text",
        event_name,
        "--timeout",
        "1",
        "--no-wrap",
    ]
    subprocess.run(command)


# Constants
CACHE_FILE = "calendar_cache.ics"
URL = getConfig()["calendarUrl"]
# Check if ical file is cached
should_download = (
    not os.path.exists(getAbsPath(CACHE_FILE)) or random.randint(1, 100) < 4
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
now = datetime.datetime.now()
events = recurring_ical_events.of(calendar).at(now)

# Display the event title in a popup
for event in events:
    title = event.get("SUMMARY", "Unknown Event")
    display_popup(title)
