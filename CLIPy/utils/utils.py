from ..database import Controller

weekdays = {'segunda': 0,
            'terça': 1,
            'quarta': 2,
            'quinta': 3,
            'sexta': 4,
            'sabado': 5,
            'domingo': 6}


def weekday_to_id(weekday: str):
    if weekday in weekdays:
        return weekdays[weekday]

    # Portuguese weekdays have the format "[word]" or "[word]-feira"
    for known_weekday in weekdays:
        simplified_weekday = weekday.split('-')[0].lower()
        if simplified_weekday in known_weekday.lower():
            return weekdays[simplified_weekday]