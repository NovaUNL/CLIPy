from bs4 import BeautifulSoup

from CLIPy.database import Controller


def parse_clean_request(request):
    soup = BeautifulSoup(request.text, 'html.parser')
    # Take useless stuff out of the way for better debugging.
    for tag in soup.find_all('script'):
        tag.decompose()
    for tag in soup.find_all('head'):
        tag.decompose()
    for tag in soup.find_all('img'):
        tag.decompose()
    for tag in soup.find_all('meta'):
        tag.decompose()
    return soup


def weekday_to_id(database: Controller, weekday: str):
    if weekday in database.__weekdays__:
        return database.__weekdays__[weekday]

    # Portuguese weekdays have the format "[word]" or "[word]-feira"
    for known_weekday in database.__weekdays__:
        if weekday.split('-')[0].lower() in known_weekday.lower():
            return database.__weekdays__[weekday]


def get_month_periods(database: Controller, month: int):
    result = []
    for period in database.get_period_set():
        if period.start_month is None or period.end_month is None:
            continue

        year_changes = period.start_month > period.end_month
        if year_changes and (month >= period.end_month or month <= period.start_month):
            result.append(period)
            break

        if not year_changes and period.start_month <= month <= period.end_month:
            result.append(period)
            break

    return result
