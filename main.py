import icalendar
import tkinter as tk
import time
import threading
import urllib.parse
import recurring_ical_events
import urllib.request
import datetime
import os
import json
import time
import argparse
from dateutil.tz import tzlocal
import subprocess
import utils
from utils import getAbsPath, getConfig, findEventName


def display_dialog(message, display_time):
    """
    Displays a dialog box with a given message for a specified amount of time.

    :param message: The message to be displayed in the dialog box.
    :param display_time: Time in seconds for which the dialog is displayed.
    """

    def on_close():
        pass  # Disable close functionality

    # Create the main window
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Create a top-level window for the dialog
    dialog_window = tk.Toplevel(root)
    dialog_window.title("Message")
    dialog_window.protocol("WM_DELETE_WINDOW", on_close)  # Disable the close button

    # Position the dialog in the center of the screen
    dialog_window.geometry(
        "+{}+{}".format(
            root.winfo_screenwidth() // 2 - dialog_window.winfo_reqwidth() // 2,
            root.winfo_screenheight() // 2 - dialog_window.winfo_reqheight() // 2,
        )
    )

    # Display the message
    tk.Label(dialog_window, text=message, padx=20, pady=20).pack()

    # Function to close the dialog after a delay
    def close_dialog():
        time.sleep(display_time)
        dialog_window.destroy()
        root.quit()

    # Run the closing function in a separate thread
    threading.Thread(target=close_dialog).start()

    root.mainloop()


def getObsidianUri(file_path, vault_root):
    # Validate input paths
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
    obsidianTabs = [tab for tab in tabs if notesAppUrlFilter in tab[0].lower()]
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
                        tabsToOpen.append([child["url"], child["name"]])
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


def replaceEvent(
    eventFilter, eventLengthHours="", eventStartTimeHours="", onlyOpen=False
):
    replacementEvents = open(getAbsPath("replacementEvents.json")).read()
    replacementEvents = json.loads(replacementEvents) if replacementEvents != "" else []
    eventName = findEventName(eventFilter)

    if eventStartTimeHours == "":
        # killProcesses(all=True)
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

    if replacementEvent != "":
        replacementEvents.append(replacementEvent)
    with open(getAbsPath("replacementEvents.json"), "w") as f:
        f.write(json.dumps(replacementEvents))


def killProcesses(all=False, obsidianNotesToOpen=[]):
    processesToKill = getConfig()["processesToKill"]
    for process in processesToKill:
        if all:
            if process[0] == "#":
                process = process[1:]
        if "obsidian" in process.lower() and process[0] != "#":
            deleteObsidianTabs(obsidianNotesToOpen)
        os.system(process)
    time.sleep(2)


def getObsidenFilesToOpen(eventTitle):
    obsidianFilesToOpen = []
    obsidianNotePaths = []
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
        pathRelativeToVault = os.path.relpath(file_path, obsidianVaultPath)
        obsidianFilesToOpen.append([getObsidianUri(file_path, obsidianVaultPath), ""])
        obsidianNotePaths.append(pathRelativeToVault)
    return obsidianFilesToOpen, obsidianNotePaths


def generateSleepTabUrl(url, title):
    # Extract the domain or title from the URL for use in the title parameter

    # Encode the URL
    encoded_url = urllib.parse.quote(url)
    encoded_title = urllib.parse.quote(title)

    # Construct the sleep tab URL with fixed sessionId and tabId
    sleep_url = f"chrome-extension://fiabciakcmgepblmdkmemdbbkilneeeh/park.html?title={encoded_title}&url={encoded_url}&tabId=1572591901&sessionId=1700014174643"

    return sleep_url


def getVsCodeCommandUris(eventName):
    eventName = eventName.lower()
    commands = []
    paths = utils.getVsCodePathsForEvent(eventName)
    for path in paths:
        command = "bash://code " + path
        commands.append([command, ""])
    return commands


def openBookmarksForNewEvents(title, setEventArg):
    tabsToOpen = getTabsToOpen(getConfig()["bookmarksFolderPath"] + "/x" + title)
    obsidianUris, obsidianNotePaths = getObsidenFilesToOpen(title)
    vsCodeCommandUris = getVsCodeCommandUris(title)
    killCommentedProcesses = True if setEventArg else False
    tabsToOpen.extend(obsidianUris)
    tabsToOpen.extend(vsCodeCommandUris)
    if tabsToOpen != []:
        if getConfig()["killUncommentedProcesses"]:
            if killCommentedProcesses:
                killProcesses(all=True, obsidianNotesToOpen=obsidianNotePaths)
            else:
                killProcesses(all=False, obsidianNotesToOpen=obsidianNotePaths)
        isFirstTab = True
        nTabsToLazyOpen = int(getConfig()["nTabsToLazyOpen"])
        i = 0
        for tab in tabsToOpen:
            tabUrl, tabTitle = tab
            if tabUrl.startswith("bash://"):
                command = (tabUrl.replace("bash://", "")).split(" ")
            elif tabUrl.startswith("http"):
                if i >= nTabsToLazyOpen:
                    tabUrl = generateSleepTabUrl(tabUrl, tabTitle)
                i += 1
                if isFirstTab:
                    command = [
                        getConfig()["browserCommand"] + " --new-window",
                        '"' + tabUrl + '"',
                    ]
                    isFirstTab = False
                else:
                    command = [getConfig()["browserCommand"], '"' + tabUrl + '"']
                time.sleep(0.07)
            elif getConfig()["notesAppUrlFilter"] in tabUrl:
                time.sleep(0.5)
                command = [getConfig()["urlOpenCommand"], '"' + tabUrl + '"']

            print("\n\n\nAbout to execute command: " + " ".join(command) + "\n\n\n")
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


def deleteObsidianTabs(obsidianNotesToOpen):
    obsidianWorkSpaceFile = (
        getConfig()["obsidianVaultPath"] + "/.obsidian/workspace.json"
    )
    contents = json.load(open(obsidianWorkSpaceFile))
    contents["main"]["id"] = ""
    contents["main"]["children"] = []
    contents["active"] = ""
    contents["lastOpenFiles"][0] = obsidianNotesToOpen[0]
    with open(obsidianWorkSpaceFile, "w") as f:
        json.dump(contents, f)


def getCurrentEvents():
    # Constants
    utils.downloadIcs()
    CACHE_FILE = "calendar_cache.ics"
    with open(getAbsPath(CACHE_FILE), "rb") as f:
        ical_string = f.read()

    replacementEvents = open(getAbsPath("replacementEvents.json")).read()
    replacementEvents = json.loads(replacementEvents) if replacementEvents != "" else []
    replacementEvents.reverse()
    for event in replacementEvents:
        if float(event["end"]) > time.time() and float(event["start"]) < time.time():
            duration_seconds = float(event["end"]) - time.time()
            return {event["name"].upper(): duration_seconds}

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
    newEvent = False
    # Display the event title and time remaining in a popup
    for event in currentEvents:
        title = event
        duration_seconds = currentEvents[event]
        if open(getAbsPath("currentEvent.txt")).read().lower() != title.lower():
            if getConfig()["autoOpen"] or setEventArg:
                if openBookmarksForNewEvents(title, setEventArg):
                    open(getAbsPath("currentEvent.txt"), "w").write(title)
            else:
                open(getAbsPath("currentEvent.txt"), "w").write(title)
            newEvent = True

        hours = duration_seconds / 3600
        message = title + " " * 15 + str(round(hours, 1))
        messageText.append(message)

    # todayIseven = datetime.datetime.today().weekday() % 2 == 0
    # spaceString = " " * 15
    # if todayIseven:
    #     messageText.insert(0, "WALK" + spaceString)
    # else:
    #     messageText.insert(0, "NO WALK" + spaceString)

    messageText = "  ||  ".join(messageText)
    if newEvent:
        display_dialog(messageText, 10)
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
