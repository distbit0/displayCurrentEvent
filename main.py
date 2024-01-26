import icalendar
import recurring_ical_events
import datetime
import os
import json
import time
import argparse
from dateutil.tz import tzlocal
import subprocess
import utils
from utils import getAbsPath, getConfig


def getTabsToOpen(title):
    path_to_folder = getConfig()["bookmarksFolderPath"] + "/x" + title
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
    notePaths = getNotePathsToOpen(title)
    vsCodeCommandUris = getVsCodeCommandUris(title, notePaths)
    tabsToOpen.extend(vsCodeCommandUris)
    return tabsToOpen


def replaceEvent(
    event_filter, event_length_hours="", event_start_time_hours="", only_open=False
):
    with open(getAbsPath("replacementEvents.json"), "r") as file:
        replacement_events = json.load(file) if os.path.getsize(file.name) > 0 else []

    event_name = utils.findEventName(event_filter)

    if event_filter == "clear":
        replacement_event = ""
    elif only_open:
        openBookmarksForNewEvents(getTabsToOpen(event_name), only_open)
        return
    else:
        event_start_time = (
            time.time()
            if not event_start_time_hours
            else utils.timeStrToUnix(event_start_time_hours)
        )
        event_end_time = event_start_time + (
            float(event_length_hours) * 3600
            if event_length_hours
            else durationOfLongestActiveEvent()
        )

        replacement_event = {
            "name": event_name,
            "start": event_start_time,
            "end": event_end_time,
        }

    if replacement_event:
        replacement_events.append(replacement_event)

    with open(getAbsPath("replacementEvents.json"), "w") as file:
        json.dump(replacement_events, file)

    if event_start_time_hours == "":
        utils.write_current_event_title("")


def getNotePathsToOpen(eventTitle):
    notePaths = []
    noteVaultPath = getConfig()["noteVaultPath"]
    compactEventTitle = "#" + eventTitle.lower().replace(" ", "")

    # Use the 'find' command to search for files containing the compact event title
    command = f"find {noteVaultPath} -type f -not -path '*/\\.*' -exec grep -l '{compactEventTitle}' {{}} \\;"
    output = subprocess.check_output(command, shell=True).decode()

    # Split the output by newline to get the file paths
    file_paths = output.strip().split("\n")
    for file_path in file_paths:
        if file_path == "":
            continue
        notePaths.append(file_path)
    return notePaths


def getVsCodeCommandUris(eventName, notePaths):
    commands = []
    vscodeEventPaths = utils.getVsCodePathsForEvent(eventName.lower())
    if vscodeEventPaths or notePaths:
        commands.append(['bash://code "' + getConfig()["noteVaultPath"] + '"', ""])
    for path in notePaths:
        commands.append(['bash://code -r "' + path + '"', ""])
    for path in vscodeEventPaths:
        commands.append(['bash://code "' + path + '"', ""])
    return commands


def openBookmarksForNewEvents(tabsToOpen, setEventArg):
    killCommentedProcesses = bool(setEventArg)
    killUncommentedProcesses = getConfig()["killUncommentedProcesses"]
    shouldKillProcesses = killUncommentedProcesses and killCommentedProcesses

    if tabsToOpen:
        utils.killProcesses(all=shouldKillProcesses)
        firstVsCodeUrl = True
        httpUrlCount = 0

        for tabUrl, tabTitle in tabsToOpen:
            if tabUrl.startswith("bash://"):
                handleBashUrl(tabUrl, firstVsCodeUrl)
                firstVsCodeUrl = False
            elif tabUrl.startswith("http"):
                handleHttpUrl(tabUrl, tabTitle, httpUrlCount)
                httpUrlCount += 1

    return bool(tabsToOpen)


def handleBashUrl(tabUrl, firstVsCodeUrl):
    command = tabUrl.replace("bash://", "").split(" ")
    time.sleep(0.14)
    utils.executeCommand(command)
    if "code" in command[0]:
        if firstVsCodeUrl:
            time.sleep(1)


def handleHttpUrl(tabUrl, tabTitle, httpUrlCount):
    def buildBrowserCommand(browserCommand, tabUrl, httpUrlCount):
        if httpUrlCount == 0:
            return [f"{browserCommand} --new-window", f'"{tabUrl}"']
        else:
            return [browserCommand, f'"{tabUrl}"']

    nTabsToLazyOpen = int(getConfig()["nTabsToLazyOpen"])
    if httpUrlCount >= nTabsToLazyOpen:
        tabUrl = utils.generateSleepTabUrl(tabUrl, tabTitle)
    time.sleep(0.14)
    utils.executeCommand(
        buildBrowserCommand(getConfig()["browserCommand"], tabUrl, httpUrlCount)
    )


def durationOfLongestActiveEvent():
    events = getCurrentEvents()
    longestDuration = 0
    for event in events:
        duration = events[event]
        if duration > longestDuration:
            longestDuration = duration

    return longestDuration


def getCurrentEvents():
    utils.downloadIcs()
    cache_file_path = getAbsPath("calendar_cache.ics")
    replacement_file_path = getAbsPath("replacementEvents.json")

    with open(cache_file_path, "rb") as file:
        ical_data = file.read()

    with open(replacement_file_path, "r") as file:
        replacement_data = file.read()
        replacement_events = json.loads(replacement_data) if replacement_data else []

    current_time = time.time()
    for event in reversed(replacement_events):
        start_time = float(event["start"])
        end_time = float(event["end"])
        if start_time < current_time < end_time:
            remaining_duration = end_time - current_time
            return {event["name"].upper(): remaining_duration}

    calendar = icalendar.Calendar.from_ical(ical_data)
    local_timezone = datetime.datetime.now(tzlocal()).tzinfo
    current_datetime = datetime.datetime.now(local_timezone)
    upcoming_events = recurring_ical_events.of(calendar).at(current_datetime)

    event_durations = {}
    for event in upcoming_events:
        event_title = event.get("SUMMARY", "Unknown Event").upper()
        event_end_time = event["DTEND"].dt
        event_duration = int((event_end_time - current_datetime).total_seconds())
        event_durations[event_title] = event_duration

    return event_durations


def process_event(title, duration_seconds, set_event_flag):
    is_new_event = False

    if utils.read_current_event_title().lower() != title.lower():
        tabs_to_open = getTabsToOpen(title)
        if tabs_to_open:
            if should_open_tabs(set_event_flag):
                openBookmarksForNewEvents(tabs_to_open, set_event_flag)
            utils.write_current_event_title(title)
            is_new_event = True

    return title, duration_seconds, is_new_event


def should_open_tabs(set_event_flag):
    return getConfig()["autoOpen"] or set_event_flag


def format_message(events):
    messages = [
        f"{title}{' ' * 15}{round(duration / 3600, 1)}" for title, duration, _ in events
    ]
    return "  ||  ".join(messages)


def main(set_event_flag):
    current_events = getCurrentEvents()
    processed_events = [
        process_event(event, current_events[event], set_event_flag)
        for event in current_events
    ]

    message_text = format_message(processed_events)
    new_event_detected = any(is_new for _, _, is_new in processed_events)

    if new_event_detected:
        utils.display_dialog(message_text, 10)

    with open(getAbsPath("displayText.txt"), "w") as file:
        file.write(message_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manages calendar events and opens corresponding tabs/windows."
    )
    parser.add_argument(
        "--setEvent",
        default="",
        type=str,
        help="Specify the name of the event to open. Use 'current' to refer to the current event.",
    )
    parser.add_argument(
        "-l", default="", type=str, help="Length of the event in hours. e.g. 4"
    )
    parser.add_argument(
        "-s", default="", type=str, help="Start time of the event. e.g., '14' for 2 PM"
    )
    parser.add_argument(
        "-o",
        action="store_true",
        help="Open tabs/windows for event without saving it. Default behavior is to save the event.",
    )
    args = parser.parse_args()
    setEvent = args.setEvent.replace("current", utils.read_current_event_title())
    if setEvent:
        replaceEvent(setEvent, args.l, args.s, args.o)
    main(setEvent)
