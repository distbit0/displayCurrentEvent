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
import json
import webbrowser
import time


def open_in_brave(url):
    # Run the process and capture the output
    subprocess.run(
        [getConfig()["browserPath"], url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def open_bookmarks(path_to_folder):
    # Load the bookmarks file
    with open(getConfig()["bookmarksFilePath"], "r") as f:
        bookmarks = json.load(f)

    # Traverse the bookmarks tree
    def traverse(node, path):
        if "name" in node:
            new_path = path + "/" + node["name"]
            if new_path.lower() == path_to_folder.lower():
                # We've found the folder, open all bookmarks in it
                for child in node["children"]:
                    if "url" in child:
                        webbrowser.open(child["url"])
            else:
                # Keep looking
                if "children" in node:
                    for child in node["children"]:
                        traverse(child, new_path)

    # Start traversal from the root
    traverse(bookmarks["roots"]["bookmark_bar"], "")


def quitBraveBrowser():
    subprocess.run(["killall", getConfig()["browerProcessName"]])


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def openBookmarksForNewEvents(title):
    if open("currentEvent.txt").read() == title:
        return
    quitBraveBrowser()
    time.sleep(0.5)
    open_bookmarks("/Bookmarks bar/Open tabs/x" + title)
    open("currentEvent.txt", "w").write(title)


def main():
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

    # Load calendar
    calendar = icalendar.Calendar.from_ical(ical_string)

    # Get events at current time
    local_tz = pytz.timezone(getConfig()["timezone"])
    now = datetime.datetime.now(local_tz)
    events = recurring_ical_events.of(calendar).at(now)

    messageText = []
    # Display the event title and time remaining in a popup
    for event in events:
        title = event.get("SUMMARY", "Unknown Event").upper()
        openBookmarksForNewEvents(title)
        end_time = event["DTEND"].dt
        duration_seconds = int((end_time - now).total_seconds())

        hours = duration_seconds / 3600
        message = title + " " * 15 + str(round(hours, 1))
        messageText.append(message)

    messageText = "  ||  ".join(messageText)
    print(messageText)


if __name__ == "__main__":
    main()
