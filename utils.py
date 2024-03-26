import json
import glob
import sqlite3
import tkinter as tk
import threading
import urllib.parse
import urllib.request
import urllib
import os
import random
import time
import datetime


def load_event_data():
    try:
        with open(getAbsPath("event_data.json"), "r") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"last_open_bookmarks_times": {}, "should_open_tabs_times": []}
    return data


def save_event_data(data):
    with open(getAbsPath("event_data.json"), "w") as file:
        json.dump(data, file)


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getAbsPath(relPath):
    basepath = os.path.dirname(__file__)
    fullPath = os.path.abspath(os.path.join(basepath, relPath))

    return fullPath


def downloadIcs(forceDownload=False, backup=False):
    CACHE_FILE = "calendar_cache.ics"
    URL = os.getenv("calendarUrl")
    # Check if ical file is cached

    should_download = (
        not os.path.exists(getAbsPath(CACHE_FILE))
        or random.randint(1, 100) < getConfig()["cacheRefreshProbability"] * 100
    ) or forceDownload
    if should_download:
        ical_string = urllib.request.urlopen(URL).read()
        if "BEGIN:VEVENT" not in ical_string.decode("utf-8"):
            print("No events found in calendar")
            return
        with open(getAbsPath(CACHE_FILE), "wb") as f:
            f.write(ical_string)

    if backup:
        currentTime = str(time.time())
        ics_file_path = (
            "modified_calendar"
            + datetime.datetime.now().strftime("%Y%m%d")
            + " | "
            + currentTime
            + " | "
            + ".ics"
        )
        with open(getAbsPath(ics_file_path), "wb") as f:
            f.write(ical_string)


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


def write_current_event_title(title):
    with open(getAbsPath("currentEvent.txt"), "w") as file:
        file.write(title)


def read_current_event_title():
    with open(getAbsPath("currentEvent.txt")) as file:
        return file.read()


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
    time.sleep(
        1.5
    )  # to wait for vsc to close, so that what we write to vscode db is not overwritten by vscode while it is shutting down
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
            cursor = conn.cursor()
            cursor.execute(
                "SELECT rowid FROM ItemTable WHERE key='memento/workbench.parts.editor'"
            )
            rowid = cursor.fetchone()
            if rowid:
                cursor.execute("DELETE FROM ItemTable WHERE rowid=?", (rowid[0],))
                conn.commit()
            else:
                print(
                    f"No memento/workbench.parts.editor row found in database: {sqlite_db_path}"
                )
    except sqlite3.Error as e:
        print(f"Error closing tabs in workspace: {e}")


def timeStrToUnix(time_string):
    if "." not in time_string:
        time_string = time_string + ".0"
    hours, minutes_fraction = map(float, time_string.split("."))
    minutes = int(minutes_fraction * 6)

    today = datetime.date.today()

    time_today = datetime.datetime(
        today.year, today.month, today.day, int(hours), minutes
    )

    return int(time.mktime(time_today.timetuple()))


def display_dialog(message, display_time):
    def on_close():
        pass  ##disable close functionality

    def close_dialog():
        time.sleep(display_time)
        dialog_window.destroy()
        root.quit()

    root = tk.Tk()
    root.withdraw()
    dialog_window = tk.Toplevel(root)
    dialog_window.title("Message")
    dialog_window.protocol("WM_DELETE_WINDOW", on_close)  # Disable the close button
    dialog_window.attributes("-topmost", True)
    dialog_window.geometry(
        "+{}+{}".format(
            root.winfo_screenwidth() // 2 - dialog_window.winfo_reqwidth() // 2,
            root.winfo_screenheight() // 2 - dialog_window.winfo_reqheight() // 2,
        )
    )

    tk.Label(dialog_window, text=message, padx=20, pady=20).pack()
    threading.Thread(target=close_dialog).start()
    root.mainloop()


if __name__ == "__main__":
    close_all_tabs_in_vscode_workspace(getConfig()["noteVaultPath"])
