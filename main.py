import icalendar
import urllib.parse
import recurring_ical_events
import urllib.request
import random
import datetime
import os
import json
import json
import time
import argparse
import urllib.parse
from dateutil.tz import tzlocal
import subprocess


def getObsidianUri(file_path, vault_root):
    # Validate input paths
    print(file_path)

    vault_name = os.path.basename(vault_root)
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            "The file path provided does not exist or is not a file."
        )
    if not os.path.isdir(vault_root):
        raise NotADirectoryError("The vault root provided is not a directory.")

    # Ensure the file path is relative to the vault root
    relative_path = os.path.relpath(file_path, vault_root)

    # Replace backslashes with forward slashes for URI compatibility
    relative_path = relative_path.replace(os.sep, "/")

    # Encode the filepath and vault name components of the URI
    encoded_vault_name = urllib.parse.quote(vault_name)
    encoded_file_path = urllib.parse.quote(relative_path)

    # Construct the Obsidian Advanced URI with the provided vault name
    # and an 'openmode' parameter set to 'tab'
    uri = f"obsidian://advanced-uri?vault={encoded_vault_name}&filepath={encoded_file_path}&openmode=tab"

    return uri


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
        return []  # None


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


def timeStrToUnix(time_string):
    # Split the string on the decimal point to separate hours and minutes
    if "." not in time_string:
        time_string = time_string + ".0"
    hours, minutes_fraction = map(float, time_string.split("."))
    # Multiply the fractional part by 60 to get the minutes as an integer
    minutes = int(minutes_fraction * 6)

    # Get the current date
    today = datetime.date.today()

    # Create a datetime object for the specified time today
    time_today = datetime.datetime(
        today.year, today.month, today.day, int(hours), minutes
    )

    # Convert the datetime object to a Unix timestamp and return it
    return int(time.mktime(time_today.timetuple()))


def findEventName(eventNameSubstring):
    eventName = ""
    events = getEventNames(getConfig()["bookmarksFolderPath"])
    for event in events:
        if eventNameSubstring.lower() in event.lower():
            eventName = event
            break
    return eventName


def replaceEvent(
    eventFilter, eventLengthHours="", eventStartTimeHours="", onlyOpen=False
):
    replacementEvents = open(getAbsPath("replacementEvents.json")).read()
    replacementEvents = json.loads(replacementEvents) if replacementEvents != "" else []
    eventName = findEventName(eventFilter)

    if eventStartTimeHours == "":
        killProcesses(all=True)
        with open(getAbsPath("currentEvent.txt"), "w") as f:
            f.write("")

    if eventFilter == "clear":
        replacementEvent = ""
    elif onlyOpen:
        openBookmarksForNewEvents(eventName)
        return
    else:
        eventStartTime = (
            time.time()
            if eventStartTimeHours == ""
            else timeStrToUnix(eventStartTimeHours)
        )

        eventEndTime = (
            time.time() + durationOfLongestActiveEvent()
            if eventLengthHours == ""
            else eventStartTime + float(eventLengthHours) * 3600
        )

        replacementEvent = {
            "name": eventName,
            "start": eventStartTime,
            "end": eventEndTime,
        }

    # if eventFilter == "clear":
    #     modifiedReplacementEvents = []
    #     for event in replacementEvents:
    #         eventName, startTime, endTime = (
    #             event["name"],
    #             event["start"],
    #             event["end"],
    #         )
    #         endTime = float(endTime)
    #         startTime = float(startTime)
    #         isNotActive = endTime < time.time() or startTime > time.time()
    #         if isNotActive:
    #             modifiedReplacementEvents.append(event)
    #     replacementEvents = list(modifiedReplacementEvents)

    if replacementEvent != "":
        replacementEvents.append(replacementEvent)
    with open(getAbsPath("replacementEvents.json"), "w") as f:
        f.write(json.dumps(replacementEvents))


def killProcesses(all=False):
    processesToKill = getConfig()["processesToKill"]
    for process in processesToKill:
        if all:
            if process[0] == "#":
                process = process[1:]
            if "obsidian" in process.lower() and process[0] != "#":
                deleteObsidianTabs()
        os.system(process)
    time.sleep(1)


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = os.path.dirname(__file__)
    fullPath = os.path.abspath(os.path.join(basepath, relPath))

    return fullPath


def getObsidenFilesToOpen(eventTitle):
    obsidianFilesToOpen = []
    obsidianVaultPath = getConfig()["obsidianVaultPath"]
    compactEventTitle = "#" + eventTitle.lower().replace(" ", "")

    # Use the 'find' command to search for files containing the compact event title
    command = f"find {obsidianVaultPath} -type f -not -path '*/\\.*' -exec grep -l '{compactEventTitle}' {{}} \\;"
    output = subprocess.check_output(command, shell=True).decode()

    # Split the output by newline to get the file paths
    file_paths = output.strip().split("\n")
    for file_path in file_paths:
        if file_path == "":
            continue
        obsidianFilesToOpen.append(getObsidianUri(file_path, obsidianVaultPath))

    return obsidianFilesToOpen


def generateSleepTabUrl(url):
    # Extract the domain or title from the URL for use in the title parameter
    title = urllib.parse.urlparse(url).netloc

    # Encode the URL
    encoded_url = urllib.parse.quote(url)

    # Construct the sleep tab URL with fixed sessionId and tabId
    sleep_url = f"chrome-extension://fiabciakcmgepblmdkmemdbbkilneeeh/park.html?title={title}&url={encoded_url}&tabId=1572532155&sessionId=1700014174643"

    return sleep_url


def openBookmarksForNewEvents(title):
    tabsToOpen = getTabsToOpen(getConfig()["bookmarksFolderPath"] + "/x" + title)
    obsidianUris = getObsidenFilesToOpen(title)
    tabsToOpen.extend(obsidianUris)
    print(tabsToOpen)
    if tabsToOpen != []:
        if getConfig()["killProcesses"]:
            killProcesses()
        isFirstTab = True
        for tab in tabsToOpen:
            if tab.startswith("bash://"):
                command = (tab.replace("bash://", "")).split(" ")
            elif tab.startswith("http"):
                if getConfig()["lazyOpenTabs"]:
                    tab = generateSleepTabUrl(tab)
                if isFirstTab:
                    command = [
                        getConfig()["browserCommand"] + " --new-window",
                        '"' + tab + '"',
                    ]
                    isFirstTab = False
                else:
                    command = [getConfig()["browserCommand"], '"' + tab + '"']
                time.sleep(0.07)
            elif getConfig()["notesAppUrlFilter"] in tab:
                time.sleep(0.5)
                print("\n\n\nAbout to execute command: " + " ".join(command) + "\n\n\n")
                command = [getConfig()["urlOpenCommand"], '"' + tab + '"']

            os.system(" ".join(command) + " &")
        return True
    return False


def durationOfLongestActiveEvent():
    events = getCurrentEvents()
    longestDuration = 0
    for event in events:
        duration = events[event]
        if duration > longestDuration:
            longestDuration = duration

    return longestDuration


def deleteObsidianTabs():
    obsidianWorkSpaceFile = (
        getConfig()["obsidianVaultPath"] + "/.obsidian/workspace.json"
    )
    contents = json.load(open(obsidianWorkSpaceFile))
    contents["main"] = {}
    with open(obsidianWorkSpaceFile, "w") as f:
        json.dump(contents, f)
    time.sleep(0.25)


def getCurrentEvents():
    # Constants
    CACHE_FILE = "calendar_cache.ics"
    URL = getConfig()["calendarUrl"]
    # Check if ical file is cached

    replacementEvents = open(getAbsPath("replacementEvents.json")).read()
    replacementEvents = json.loads(replacementEvents) if replacementEvents != "" else []
    replacementEvents.reverse()
    for event in replacementEvents:
        if float(event["end"]) > time.time() and float(event["start"]) < time.time():
            duration_seconds = float(event["end"]) - time.time()
            return {event["name"].upper(): duration_seconds}

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
    ## get name of my current timezone

    local_tz = datetime.datetime.now(tzlocal()).tzinfo
    now = datetime.datetime.now(local_tz)
    events = recurring_ical_events.of(calendar).at(now)
    finalEvents = {}
    for event in events:
        title = event.get("SUMMARY", "Unknown Event").upper()
        end_time = event["DTEND"].dt
        duration_seconds = int((end_time - now).total_seconds())
        finalEvents[title] = duration_seconds

    return finalEvents


def main(setEventArg):
    currentEvents = getCurrentEvents()
    messageText = []
    # Display the event title and time remaining in a popup
    for event in currentEvents:
        title = event
        duration_seconds = currentEvents[event]
        if open(getAbsPath("currentEvent.txt")).read().lower() != title.lower():
            if getConfig()["autoOpen"] or setEventArg:
                if openBookmarksForNewEvents(title):
                    open(getAbsPath("currentEvent.txt"), "w").write(title)
            else:
                open(getAbsPath("currentEvent.txt"), "w").write(title)
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
    parser.add_argument(
        "-s", default="", type=str
    )  # start time of event e.g. 14 = 2pm and 9 = 9am
    parser.add_argument(
        "-o", action="store_true"
    )  # whether to just only open the tabs/windows rather than also saving the event

    args = parser.parse_args()
    if args.setEvent != "":
        replaceEvent(args.setEvent, args.l, args.s, args.o)
    main(args.setEvent)
