import json
import glob
import sqlite3
import tkinter as tk
import urllib.parse
import urllib.request
import urllib
import os
import time
from dotenv import load_dotenv

load_dotenv()


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = os.path.dirname(__file__)
    fullPath = os.path.abspath(os.path.join(basepath, relPath))

    return fullPath


def findEventName(eventNameSubstring):
    eventName = ""
    events = getEventNames(getConfig()["bookmarksFolderPath"])
    for event in events:
        if eventNameSubstring.lower() in event.lower():
            eventName = event
            break
    return eventName


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


def getVsCodePathsForEvent(eventName):
    with open(getAbsPath("./vsCodeEventPaths.json"), "r") as file:
        directoryMap = json.load(file)
    if eventName not in directoryMap:
        return []
    return directoryMap[eventName]


def executeCommand(command):
    if type(command) == list:
        fullCommand = " ".join(command) + " &"
    else:
        fullCommand = command
    print(f"\n\n\nAbout to execute command: {fullCommand}\n\n\n")
    os.system(fullCommand)


def generateSleepTabUrl(url, title):
    encoded_url = urllib.parse.quote(url)
    encoded_title = urllib.parse.quote(title)
    sleep_url = f"chrome-extension://fiabciakcmgepblmdkmemdbbkilneeeh/park.html?title={encoded_title}&url={encoded_url}&tabId=1572591901&sessionId=1700014174643"

    return sleep_url


def killProcesses(all=False):
    processesToKill = getConfig()["processesToKill"]
    for process in processesToKill:
        if all:
            if process[0] == "#":
                process = process[1:]
        print(f"Killing process: {process}")
        executeCommand(process)
        if "code" in process.lower() and process[0] != "#":
            close_all_tabs_in_vscode_workspace(getConfig()["noteVaultPath"])
    time.sleep(2)


def find_workspace_config_dir(workspace_storage, workspace_folder_name):
    stateFileDirs = []
    for pattern in ["workspace.json", "meta.json"]:
        for state_file in glob.glob(
            f"{workspace_storage}/**/{pattern}", recursive=True
        ):
            with open(state_file, "r") as file:
                state_data = json.load(file)
                inNotesField = workspace_folder_name in state_data.get("name", "")
                inFolderField = workspace_folder_name in state_data.get("folder", "")
                if inNotesField or inFolderField:
                    print(f"Found workspace config dir: {state_file}", state_data)
                    stateFileDirs.append(state_file.replace(pattern, ""))
    return stateFileDirs


def close_all_tabs_in_vscode_workspace(workspace_path):
    # to wait for vsc to close, so that what we write to vscode db is not overwritten by vscode while it is shutting down
    time.sleep(3)
    workspace_path = workspace_path.rstrip("/")
    workspace_storage = os.path.expanduser("~/.config/Code/User/workspaceStorage/")
    workspace_folder_name = workspace_path.split("/")[-1]
    config_dirs = find_workspace_config_dir(workspace_storage, workspace_folder_name)

    if not config_dirs:
        print(
            f"No workspace state file found for workspace: {workspace_path}. Could not close tabs."
        )
        return
    for config_dir in config_dirs:
        close_tabs_in_workspace(config_dir)


def close_tabs_in_workspace(config_dir):
    backup_db_path = os.path.join(config_dir, "state.vscdb.backup")
    sqlite_db_path = os.path.join(config_dir, "state.vscdb")

    if os.path.exists(backup_db_path):
        os.remove(backup_db_path)
        print(f"Removed backup database: {backup_db_path}")

    try:
        with sqlite3.connect(sqlite_db_path) as conn:
            keys = ["memento/workbench.parts.editor"]  # , "history.entries"]
            for key in keys:
                cursor = conn.cursor()
                cursor.execute("SELECT rowid FROM ItemTable WHERE key=?", (key,))
                rowid = cursor.fetchone()
                if rowid:
                    cursor.execute("DELETE FROM ItemTable WHERE rowid=?", (rowid[0],))
                    conn.commit()
                    print(f"deleted all tabs in workspace: {config_dir}", key)
                else:
                    print(f"No {key} row found in database: {sqlite_db_path}")
    except sqlite3.Error as e:
        print(f"Error closing tabs in workspace: {e}")
