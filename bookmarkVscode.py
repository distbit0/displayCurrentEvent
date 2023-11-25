import os
import json
import sys
from utils import getAbsPath, findEventName


def manageEventPaths(eventName, currentPath):
    directoryMapFilePath = getAbsPath("./vsCodeEventPaths.json")
    if not os.path.exists(directoryMapFilePath):
        with open(directoryMapFilePath, "w") as file:
            json.dump({}, file)

    with open(directoryMapFilePath, "r") as file:
        directoryMap = json.load(file)

    if eventName in directoryMap:
        if currentPath in directoryMap[eventName]:
            directoryMap[eventName].remove(currentPath)
            print(f"Removed '{currentPath}' from project '{eventName}'.")
        else:
            directoryMap[eventName].append(currentPath)
            print(f"Added '{currentPath}' to project '{eventName}'.")
    else:
        directoryMap[eventName] = [currentPath]
        print(f"Added '{currentPath}' to new project '{eventName}'.")

    with open(directoryMapFilePath, "w") as file:
        json.dump(directoryMap, file, indent=4)


def getEventsForPath(currentDir):
    events = []
    with open(getAbsPath("./vsCodeEventPaths.json"), "r") as file:
        directoryMap = json.load(file)
    for event in directoryMap:
        if currentDir in directoryMap[event]:
            events.append(event)
    return events


if __name__ == "__main__":
    currentPath = os.getcwd()
    if len(sys.argv) == 1:
        print("\n".join(getEventsForPath(currentPath)))
    elif len(sys.argv) == 2:
        eventSubString = sys.argv[1]
        eventName = findEventName(eventSubString).lower()
        manageEventPaths(eventName, currentPath)
