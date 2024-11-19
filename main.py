import pysnooper
import os
import json
import time
import argparse
import subprocess
import utils
import re
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
                        if child["name"] == "SHARE":
                            continue
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
    return tabsToOpen, notePaths


def getNotePathsToOpen(eventTitle):
    notePaths = []
    noteVaultPath = getConfig()["noteVaultPath"]
    compactEventTitle = "$" + eventTitle.lower().replace(" ", "")

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


def openBookmarksForNewEvents(tabsToOpen):
    if not tabsToOpen:
        return False

    # utils.killProcesses(all=True)
    firstVsCodeUrl = True
    httpUrlCount = 0

    for tabUrl, tabTitle in tabsToOpen:
        if tabUrl.startswith("bash://"):
            handleBashUrl(tabUrl, firstVsCodeUrl)
            firstVsCodeUrl = False
        elif tabUrl.startswith("http"):
            handleHttpUrl(tabUrl, tabTitle, httpUrlCount)
            httpUrlCount += 1

    return True


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
    nTabsToOpen = int(getConfig()["nTabsToOpen"])
    if httpUrlCount >= nTabsToOpen:
        return
    if httpUrlCount >= nTabsToLazyOpen:
        tabUrl = utils.generateSleepTabUrl(tabUrl, tabTitle)
    time.sleep(0.14)
    utils.executeCommand(
        buildBrowserCommand(getConfig()["browserCommand"], tabUrl, httpUrlCount)
    )


def remove_links(text):
    # Remove [[wikilink]]
    text = re.sub(r"(\[\[)|(\]\])", "", text)

    # Remove [google](https://google.com) using the pattern
    text = re.sub(r"\[([^]]*)]\([^)]*\)", r"\1", text)

    return text


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
    args = parser.parse_args()
    if args.setEvent:
        event_name = utils.findEventName(args.setEvent)
        if event_name:
            openBookmarksForNewEvents(getTabsToOpen(event_name)[0])
            getNotePathsToOpen(event_name)