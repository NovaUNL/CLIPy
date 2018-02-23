from bs4 import BeautifulSoup

from CLIPy.database import Controller

weekdays = {'segunda': 0, 'terça': 1, 'terca': 1, 'quarta': 2, 'quinta': 3,
           'sexta': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6}


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


def weekday_to_id(weekday: str):
    if weekday in weekdays:
        return weekdays[weekday]

    # Portuguese weekdays have the format "[word]" or "[word]-feira"
    for known_weekday in weekdays:
        simplified_weekday = weekday.split('-')[0].lower()
        if simplified_weekday in known_weekday.lower():
            return weekdays[simplified_weekday]


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
