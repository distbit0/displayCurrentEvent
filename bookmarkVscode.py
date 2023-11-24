import os
import json
import sys
from utils import getAbsPath, findEventName


def manageEventPaths(eventName, directoryMapFilePath):
    currentPath = os.getcwd()
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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <project_name>")
        sys.exit(1)

    eventSubString = sys.argv[1]
    eventName = findEventName(eventSubString)
    directoryMapFilePath = getAbsPath("./vsCodeEventPaths.json")
    manageEventPaths(eventName, directoryMapFilePath)
