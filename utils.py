import json
import os


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
