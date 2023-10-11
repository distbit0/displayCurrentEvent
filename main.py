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


def sortObsidianToEnd(tabs):
    obsidianTabs = [
        obsidianTab
        for obsidianTab in tabs
        if "obsidian://open?vault" in obsidianTab.lower()
    ]
    for tab in obsidianTabs:
        tabs.remove(tab)
    tabs.extend(obsidianTabs)
    return tabs


def getTabsToOpen(path_to_folder):
    # Load the bookmarks file
    tabsToOpen = []
    foundFolder = []
    with open(getConfig()["bookmarksFilePath"], "r") as f:
        bookmarks = json.load(f)

    # Traverse the bookmarks tree
    def traverse(node, path):
        if "name" in node:
            new_path = path + "/" + node["name"]
            if new_path.lower() == path_to_folder.lower():
                foundFolder.append(True)
                for child in node["children"]:
                    if "url" in child:
                        tabsToOpen.append(child["url"])
            else:
                # Keep looking
                if "children" in node:
                    for child in node["children"]:
                        traverse(child, new_path)

    # Start traversal from the root
    traverse(bookmarks["roots"]["bookmark_bar"], "")

    tabsToOpen = sortObsidianToEnd(tabsToOpen)

    if foundFolder:
        return tabsToOpen
    else:
        return None


def quitBraveBrowser():
    subprocess.run(
        ["killall", getConfig()["browserProcessName"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def executeBrowserStartupCommands():
    for command in getConfig()["browserStartupCommands"]:
        subprocess.Popen(
            command.split(" "),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def openBookmarksForNewEvents(title):
    pathToCurrentEventFile = getAbsPath("currentEvent.txt")
    if open(pathToCurrentEventFile).read() == title:
        return

    tabsToOpen = getTabsToOpen("/Bookmarks bar/Open tabs/x" + title)
    if tabsToOpen != None:
        quitBraveBrowser()
        executeBrowserStartupCommands()
        time.sleep(2)
        for tab in tabsToOpen:
            subprocess.run(
                [getConfig()["browserCommand"], tab],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        open(pathToCurrentEventFile, "w").write(title)
        return


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
