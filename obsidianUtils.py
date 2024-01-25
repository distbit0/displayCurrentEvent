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
