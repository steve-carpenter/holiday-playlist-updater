import re
import requests
from datetime import datetime, timedelta, timezone
import os

SCREENLY_TOKEN = os.getenv('SCREENLY_TOKEN')
CALENDARIFIC_TOKEN = os.environ.get('CALENDARIFIC_TOKEN')
START_HOLIDAY = 1
END_HOLIDAY = 2
START_HOLIDAY_OFFSET = 3
END_HOLIDAY_OFFSET = 4
RANGE_PATTERN = "^([\w\s\d]+)\|(?:(\d+)|(?:(['A-Za-z\s]+)(?:(?:\+)([\d]+))*))\|(?:(\d+)|(?:(['A-Za-z\s]+)(?:(?:\+)([\d]+))*))$"
PATTERN = re.compile(RANGE_PATTERN)


def get_screenly_headers() -> dict:
    headers = {
        "Authorization": f"Token {SCREENLY_TOKEN}",
        "Content-Type": "application/json"
    }
    return headers


def get_holiday_headers() -> dict:
    return {"API_KEY": f"{CALENDARIFIC_TOKEN}"}


def get_current_year() -> str:
    return datetime.now().year


def get_screenly_playlists() -> dict:
    response = requests.request(
        method='GET',
        url='https://api.screenlyapp.com/api/v3/playlists/',
        headers=get_screenly_headers()
    )
    return response.json() if response.ok else {}

def get_holidays(country: str = "US", year: int = get_current_year()):
    response = requests.request(
        method='GET',
        url='https://calendarific.com/api/v2/holidays?',
        params={"api_key": get_holiday_headers(
        )['API_KEY'], "country": country, "year": year}
    )
    return {holiday['name']: holiday['date']['iso']
            for holiday in response.json()['response']['holidays']
            } if response.ok else {}


def iso_to_ms(date: str, delta: int = 0) -> int:
    date_obj = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    date_obj += timedelta(days=delta)
    return int(date_obj.timestamp() * 1000)


def create_date(date: str, delta: int = 0) -> int:
    date_obj = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    date_obj += timedelta(days=delta)
    return date_obj.isoformat()


def update_playlist(playlist: dict, new_predicate: str):
    if playlist.get('id'):
        if new_predicate and playlist['predicate'] != new_predicate:
            response = requests.request(
                method='PATCH',
                url=f'https://api.screenlyapp.com/api/v3/playlists/{playlist.get("id")}/',
                json={'predicate': new_predicate},
                headers=get_screenly_headers()
            )
            print(f'{playlist.get("title")} updated' if response.ok else "")
        else:
            print(f"{playlist['title']} not updated because predicate didn't change")


def regex_to_values(playlist_title, holidays):
    regex_result = PATTERN.match(playlist_title)
    start_offset = regex_result.group(2)
    start_date = holidays.get(regex_result.group(3))
    start_date_delta = regex_result.group(4)
    end_offset = regex_result.group(5)
    end_date = holidays.get(regex_result.group(6))
    end_date_delta = regex_result.group(7)
    return start_offset, start_date, start_date_delta, end_offset, end_date, end_date_delta


def process_playlists(playlists: list, holidays: dict):
    print(f"Comparing {len(playlists)} playlists & {len(holidays)} holidays...")
    for playlist in playlists:
        if playlist['is_enabled'] == False:
            print(f"{playlist['title']} skipped because it's disabled")
            continue
        elif '|' in playlist['title']:
            final_start_date = final_end_date = None
            start_offset, start_date, start_date_delta, end_offset, end_date, end_date_delta = regex_to_values(
                playlist['title'], holidays)
            # Grab & update groups from regex
            if not start_date and not end_date:
                print("Invalid expression; need a date to reference")
                continue

            if start_date and start_date_delta:
                final_start_date = create_date(start_date, int(start_date_delta))
            elif start_offset and end_date:
                final_start_date = create_date(end_date, -int(start_offset))
            elif start_date:
                final_start_date = start_date

            if end_date and end_date_delta:
                final_end_date = create_date(end_date, int(end_date_delta))
            elif end_offset and start_date:
                final_end_date = create_date(start_date, int(end_offset))
            elif end_date:
                final_end_date = end_date

            # Grab & update groups from regex
            if final_start_date and final_end_date:
                update_playlist(playlist, f'TRUE AND ($DATE >= {iso_to_ms(final_start_date)}) AND ($DATE <= {iso_to_ms(final_end_date)})')
        else:
            holiday = holidays.get(playlist['title'])
            if holiday:
                update_playlist(playlist,  f'TRUE AND ($DATE = {iso_to_ms(holiday)})')
            else:
                print(f"{playlist['title']} skipped because it's not a holiday")


def main():
    process_playlists(get_screenly_playlists(), get_holidays())


if __name__ == '__main__':
    main()
