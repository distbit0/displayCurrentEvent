import os
import subprocess
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from tzlocal import get_localzone
import time
import utils
from dotenv import load_dotenv

load_dotenv()


# Load Google Calendar API credentials
def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", ["https://www.googleapis.com/auth/calendar"]
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", ["https://www.googleapis.com/auth/calendar"]
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def delete_all_events(service, batch_size=1000):
    calendar_id = os.getenv("calendarId")
    alreadyDeletedIds = []

    def main():
        def getAllEventIds():
            page_token = None
            all_ids = []
            while True:
                events_result = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        singleEvents=False,
                        showDeleted=False,
                        maxResults=2500,
                        pageToken=page_token,
                    )
                    .execute()
                )
                events = events_result.get("items", [])
                page_token = events_result.get("nextPageToken")
                print(f"Fetched {len(events)} events")

                recurringEventIds = [
                    event["recurringEventId"]
                    for event in events
                    if "recurringEventId" in event
                ]
                ids = [event["id"] for event in events if "id" in event]
                all_ids.extend(list(set(recurringEventIds + ids)))

                if not page_token:
                    break
            return all_ids

        ids = getAllEventIds()
        print(f"Total {len(ids)} events to delete")

        print(f"Deleting {len(ids)} events in batches")
        i = 0
        ids = list(set(ids) - set(alreadyDeletedIds))
        while True:
            batch = service.new_batch_http_request()
            startIndex = i * batch_size
            endIndex = min((i + 1) * batch_size, len(ids))
            idsToDelete = ids[startIndex:endIndex]
            print(f"Batch {i}: Deleting events from {startIndex} to {endIndex}")

            for id in idsToDelete:
                batch.add(
                    service.events().delete(
                        calendarId=calendar_id,
                        eventId=id,
                    )
                )
                print(f"Deleted event: {id}")
                alreadyDeletedIds.append(id)

            try:
                batch.execute()
            except Exception as e:
                print(e)

            i += 1
            if endIndex >= len(ids):
                break
        return ids

    noEventsToDelete = True
    while True:
        try:
            ids = main()
            if not ids:
                return noEventsToDelete
            else:
                print("still deleting", "remaining ids:", len(ids), ":", ids)
        except Exception as e:
            print(e)
            time.sleep(20)
        noEventsToDelete = False


# Function to add events from an ICS file


def get_event_timezone():
    event_timezone_id = "iuihhugfrudtyfygugugguy"
    with open(utils.getAbsPath("calendar_cache.ics")) as f:
        text = f.read()
    for line in text.split("\n"):
        if "TZID=" in line:
            event_timezone_id = ":".join(line.split("TZID=")[1].split(":")[:-1])
            break

    return event_timezone_id.strip()


def modifyIcs(old_tz, new_tz):
    with open(utils.getAbsPath("calendar_cache.ics")) as f:
        text = f.read()
    print("replacing " + old_tz + " with " + new_tz)
    text = str(text.replace(old_tz, new_tz))
    tzDefStart, tzDefEnd = text.find("BEGIN:VTIMEZONE"), text.find(
        "END:VTIMEZONE"
    ) + len("END:VTIMEZONE")
    text = str(text.replace(text[tzDefStart:tzDefEnd], ""))
    text = "\n".join([line for line in text.splitlines() if "DTSTAMP" not in line])
    currentDate = time.strftime("%Y-%m-%d")
    with open(utils.getConfig()["newIcsSavePath"] + currentDate + ".ics", "w") as f:
        f.write(text)


def open_in_brave(url):
    subprocess.run(["xdg-open", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


service = get_calendar_service()
currentTz = str(get_localzone())
gCalTz = get_event_timezone()
print(f"Current timezone: {currentTz}, Google Calendar timezone: {gCalTz}")

if gCalTz.lower() != currentTz.lower():
    utils.downloadIcs(forceDownload=True, backup=True)
    gCalTz = get_event_timezone()
    if gCalTz.lower() != currentTz.lower():
        noEventsToDelete = delete_all_events(service)
        if not noEventsToDelete:
            modifyIcs(gCalTz, currentTz)
        open_in_brave("https://calendar.google.com/calendar/u/0/r/settings/export")
