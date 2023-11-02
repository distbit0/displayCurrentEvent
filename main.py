import icalendar
import recurring_ical_events
import urllib.request
import random
import datetime
import subprocess
import os
from os import path
import json
import pytz
import json
import time
import argparse


def sortObsidianToEnd(tabs):
    notesAppUrlFilter = getConfig()["notesAppUrlFilter"]
    obsidianTabs = [tab for tab in tabs if notesAppUrlFilter in tab.lower()]
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


def getEventNames(path_to_folder):
    subfolderNames = []
    foundFolder = []

    # Load bookmarks from the specified path in the config
    with open(getConfig()["bookmarksFilePath"], "r") as f:
        bookmarks = json.load(f)

    def traverse(node, path):
        if "name" in node:
            new_path = path + "/" + node["name"]
            if new_path.lower() == path_to_folder.lower():
                foundFolder.append(True)
                for child in node.get("children", []):
                    if "children" in child:
                        subfolderNames.append(child["name"][1:])
            else:
                if "children" in node:
                    for child in node["children"]:
                        traverse(child, new_path)

    traverse(bookmarks["roots"]["bookmark_bar"], "")

    if foundFolder:
        return subfolderNames
    else:
        return None


def setCurrentEvent(eventFilter, eventLengthHours="", hoursUntilEvent=""):
    if eventFilter == "clear":
        replacementEvent = ""
    else:
        events = getEventNames(getConfig()["bookmarksFolderPath"])
        for event in events:
            if eventFilter.lower() in event.lower():
                eventName = event
                break
        if hoursUntilEvent == "":
            eventStartTime = time.time()
        else:
            eventStartTime = time.time() + float(hoursUntilEvent) * 3600
        if eventLengthHours == "":
            latestEndTime = time.time() + getEndTimeOfLongestEvent()
        else:
            latestEndTime = eventStartTime + float(eventLengthHours) * 3600

        replacementEvent = json.dumps(
            {"name": eventName, "start": eventStartTime, "end": latestEndTime}
        )

    killProcesses(all=True)
    with open(getAbsPath("replacementEvent.txt"), "w") as f:
        f.write(replacementEvent)
    if hoursUntilEvent == "" and eventFilter != "clear":
        with open(getAbsPath("currentEvent.txt"), "w") as f:
            f.write("")


def killProcesses(all=False):
    processesToKill = getConfig()["processesToKill"]
    for process in processesToKill:
        if all:
            process = process.replace("#", "")
        print("pkill --signal 2 " + process)
        os.system("pkill --signal 2 " + process)
    time.sleep(1)


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
    pathToCurrentEventFile = getAbsPath("currentEvent.txt")
    if open(pathToCurrentEventFile).read().lower() == title.lower():
        return

    tabsToOpen = getTabsToOpen(getConfig()["bookmarksFolderPath"] + "/x" + title)
    if tabsToOpen != None:
        if getConfig()["killProcesses"]:
            killProcesses()
        isFirstTab = True
        for tab in tabsToOpen:
            if tab.startswith("bash://"):
                command = (tab.replace("bash://", "")).split(" ")
            else:
                if isFirstTab and tab.startswith("http"):
                    command = [getConfig()["browserCommand"], '"' + tab + '"']
                    isFirstTab = False
                else:
                    command = [getConfig()["urlOpenCommand"], '"' + tab + '"']
                time.sleep(0.07)
            if getConfig()["notesAppUrlFilter"] in tab:
                time.sleep(0.5)
            print(" ".join(command) + " &")
            os.system(" ".join(command) + " &")
        open(pathToCurrentEventFile, "w").write(title)
        return


def getEndTimeOfLongestEvent():
    events = getCurrentEvents()
    longestDuration = 0
    for event in events:
        duration = events[event]
        if duration > longestDuration:
            longestDuration = duration

    return longestDuration


def getCurrentEvents():
    # Constants
    CACHE_FILE = "calendar_cache.ics"
    URL = getConfig()["calendarUrl"]
    # Check if ical file is cached

    replacementEvent = open(getAbsPath("replacementEvent.txt")).read()
    if replacementEvent != "":
        replacementEvent = json.loads(replacementEvent)
        eventName, startTime, endTime = (
            replacementEvent["name"],
            replacementEvent["start"],
            replacementEvent["end"],
        )
        endTime = float(endTime)
        startTime = float(startTime)
        if endTime > time.time() and startTime < time.time():
            duration_seconds = endTime - time.time()
            return {eventName.upper(): duration_seconds}

    should_download = (
        not path.exists(getAbsPath(CACHE_FILE))
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
    finalEvents = {}
    for event in events:
        title = event.get("SUMMARY", "Unknown Event").upper()
        end_time = event["DTEND"].dt
        duration_seconds = int((end_time - now).total_seconds())
        finalEvents[title] = duration_seconds

    return finalEvents


def main():
    finalEvents = getCurrentEvents()
    messageText = []
    # Display the event title and time remaining in a popup
    for event in finalEvents:
        title = event
        duration_seconds = finalEvents[event]
        openBookmarksForNewEvents(title)
        hours = duration_seconds / 3600
        message = title + " " * 15 + str(round(hours, 1))
        messageText.append(message)

    # determine if today is an odd or even day
    todayIseven = datetime.datetime.today().weekday() % 2 == 0
    spaceString = " " * 15
    if todayIseven:
        messageText.insert(0, "WALK" + spaceString)
    else:
        messageText.insert(0, "NO WALK" + spaceString)

    messageText = "  ||  ".join(messageText)
    with open(getAbsPath("displayText.txt"), "w") as f:
        f.write(messageText)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calendar event manager")
    parser.add_argument("--setEvent", default="", type=str)
    parser.add_argument("-l", default="", type=str)  ## length of event in hours
    parser.add_argument("-s", default="", type=str)  # hours until start of event

    args = parser.parse_args()
    if args.setEvent != "":
        if args.l != "":
            setCurrentEvent(args.setEvent, args.l, args.s)
        else:
            setCurrentEvent(args.setEvent)
    main()
