import os
import pytz
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from icalendar import Calendar, Event
import dateutil.parser
from icalendar import vRecur
from tzlocal import get_localzone
import time
import utils


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


def convert_rrule_value(key, value):
    if key == "UNTIL":
        # Parse UNTIL as datetime
        return datetime.datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    elif key == "INTERVAL":
        # Parse INTERVAL as integer
        return int(value)
    elif key == "BYDAY":
        # BYDAY can be a single day or a list of days, return as is
        return value.split(",") if "," in value else value
    else:
        # Return other values as they are (e.g., FREQ as string)
        return value


# Function to export events to an ICS file with timezone adjustment
def export_events_to_ics(service, calendar_id, ics_file_path):
    cal = Calendar()
    events_result = service.events().list(calendarId=calendar_id).execute()
    events = events_result.get("items", [])
    print(len(events))
    for event in events:
        ical_event = Event()
        print(event["status"])
        if event["status"] == "cancelled":
            continue
        print(event)
        # Convert and add start and end times
        start_dt = dateutil.parser.parse(event["start"]["dateTime"])
        end_dt = dateutil.parser.parse(event["end"]["dateTime"])

        ical_event.add("dtstart", start_dt)
        ical_event.add("dtend", end_dt)
        ical_event.add("summary", event["summary"])

        if "recurrence" in event:
            for rrule_str in event["recurrence"]:
                if rrule_str.startswith("RRULE:"):
                    rrule_properties = rrule_str.replace("RRULE:", "").split(";")
                    rrule_dict = {
                        prop.split("=")[0].lower(): convert_rrule_value(
                            prop.split("=")[0], prop.split("=")[1]
                        )
                        for prop in rrule_properties
                    }
                    rrule = vRecur(rrule_dict)
                    ical_event.add("rrule", rrule)

        cal.add_component(ical_event)
        cal.to_ical()

    with open(ics_file_path, "wb") as f:
        f.write(cal.to_ical())


# Function to delete all events in a calendar


def delete_all_events(service, calendar_id, batch_size=50):
    def main():
        events_result = (
            service.events()
            .list(calendarId=calendar_id, singleEvents=True, showDeleted=False)
            .execute()
        )
        events = events_result.get("items", [])

        # If there are no more events, exit the loop
        if not events:
            return True

        print(f"Deleting {len(events)} events in batches")

        # Delete events in batches
        batch = service.new_batch_http_request()
        for event in events[:batch_size]:
            if event["status"] != "cancelled":
                try:
                    print(event, "\n\n\n\n\n\n")
                    batch.add(
                        service.events().delete(
                            calendarId=calendar_id, eventId=event["recurringEventId"]
                        )
                    )

                    batch.add(
                        service.events().delete(
                            calendarId=calendar_id, eventId=event["id"]
                        )
                    )
                except Exception as e:
                    # Handle errors if needed
                    pass
            else:
                print(" cancelled event")

        # Execute the batch request
        try:
            batch.execute()
        except Exception as e:
            # Handle batch execution errors if needed
            print(e)
            pass

    while True:
        try:
            finished = main()
            if finished:
                break
        except Exception as e:
            print(e)
            time.sleep(20)


# Function to add events from an ICS file
def add_events_from_ics(service, calendar_id, ics_file_path, timezone_str):
    with open(ics_file_path, "rb") as f:
        gcal = Calendar.from_ical(f.read())
    timezone = pytz.timezone(timezone_str)

    def callback(request_id, response, exception):
        if exception is not None:
            print(f"An error occurred: {exception}")
        else:
            print(f"Event created: {response.get('htmlLink')}")

    batch = service.new_batch_http_request(callback=callback)
    for component in gcal.walk():
        if component.name == "VEVENT":
            # Extract and adjust start and end times
            start_time = component.get("dtstart").dt
            end_time = component.get("dtend").dt

            if not start_time.tzinfo:
                start_time = timezone.localize(start_time)
            else:
                start_time = start_time.astimezone(timezone)

            if not end_time.tzinfo:
                end_time = timezone.localize(end_time)
            else:
                end_time = end_time.astimezone(timezone)

            # Prepare the event dictionary
            event = {
                "summary": str(component.get("summary")),
                "start": {"dateTime": start_time.isoformat(), "timeZone": timezone_str},
                "end": {"dateTime": end_time.isoformat(), "timeZone": timezone_str},
            }

            # Handle recurrence
            if component.get("rrule"):
                rrule = (
                    component.get("rrule")
                    .to_ical()
                    .decode("utf-8")
                    .replace("\r\n ", "")
                    .replace("\n ", "")
                )
                if "UNTIL" in rrule:
                    # Extract UNTIL value and adjust its timezone
                    until_value = rrule.split("UNTIL=")[1].split(";")[0]
                    until_local = datetime.datetime.strptime(
                        until_value, "%Y%m%dT%H%M%S"
                    )
                    until_local = timezone.localize(until_local)
                    rrule = rrule.replace(
                        until_value, until_local.strftime("%Y%m%dT%H%M%SZ")
                    )

                event["recurrence"] = [f"RRULE:{rrule}"]

            # Insert the event
            batch.add(service.events().insert(calendarId=calendar_id, body=event))

    # Execute the batch request
    batch.execute()


def get_event_timezone(calendar_id, service):
    # Initialize the Google Calendar service

    # Get the first event from the calendar
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id, maxResults=1, showDeleted=False, singleEvents=True
        )
        .execute()
    )
    events = events_result.get("items", [])
    if not events:
        return None  # No events found in the calendar

    # Get the timezone ID of the event
    event_timezone_id = events[0].get("start", {}).get("timeZone")

    return event_timezone_id


# Main execution
SCOPES = ["https://www.googleapis.com/auth/calendar"]
calendar_id = "28a27e8ffdf1bfc180f78f96f1992f8dbb60e000ac88306236041c181c54f5fe@group.calendar.google.com"

service = get_calendar_service()

currentTz = str(get_localzone())
gCalTz = get_event_timezone(calendar_id, service)
print(f"Current timezone: {currentTz}, Google Calendar timezone: {gCalTz}")
if gCalTz.lower() != currentTz.lower():
    # Export events to ICS file with new timezone
    utils.downloadIcs(forceDownload=True, backup=True)
    # # # Delete all events in the Google Calendar
    # delete_all_events(service, calendar_id)

    # # # Re-import events from the ICS file
    # add_events_from_ics(service, calendar_id, currentTz)
