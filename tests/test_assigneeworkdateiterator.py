import datetime
import pytest
from qlu.core import AssigneeWorkDateIterator


DATE_MONDAY = datetime.date(2019, 6, 3)


def test_assigneeworkdateiterator_default():
    workdate_iterator = AssigneeWorkDateIterator(
        username='testuser',
        start_date=DATE_MONDAY
    )

    # iterate over 7 days to get through a whole week
    start_day = 3
    for i in range(5):
        day = next(workdate_iterator)
        assert day.month == 6
        assert day.day == start_day
        start_day += 1

    # confirm that the next date is the following monday
    next_day = next(workdate_iterator)
    expected_day = 10
    assert next_day.day == expected_day, f'actual({next_day}) != expected({datetime.date(2019, 6, 10)}'


def test_assigneeworkdateiterator_singleworkday():
    workdate_iterator = AssigneeWorkDateIterator(
        username='testuser',
        workdays=[
            'Fri',
        ],
        start_date=DATE_MONDAY
    )
    expected_date = datetime.date(2019, 6, 7)
    # iterate over 7 days to get through a whole week
    actual_date = next(workdate_iterator)

    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'

    # check that the next date is the next friday
    next_expected_date = datetime.date(2019, 6, 14)
    next_actual_date = actual_date = next(workdate_iterator)
    assert next_actual_date == next_expected_date, f'actual({next_actual_date}) != expected({next_expected_date}'


def test_assigneeworkdateiterator_invalid_workday_value():
    with pytest.raises(ValueError) as e:
        workdate_iterator = AssigneeWorkDateIterator(
            username='testuser',
            workdays=[
                'Tue',
                'Kin',
                'Mon'
            ],
            start_date=DATE_MONDAY
        )


def test_assigneeworkdateiterator_with_personal_holidays():
    holidays = [
        datetime.date(2019, 6, 4),  # tuesday
        datetime.date(2019, 6, 5),  # wednesday
        datetime.date(2019, 6, 6),  # thursday
    ]
    workdate_iterator = AssigneeWorkDateIterator(
        username='testuser',
        personal_holidays=holidays,
        start_date=DATE_MONDAY
    )
    # monday
    expected_date = datetime.date(2019, 6, 3)
    actual_date = next(workdate_iterator)
    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'

    # friday
    expected_date = datetime.date(2019, 6, 7)
    actual_date = next(workdate_iterator)
    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'

    # the next monday
    expected_date = datetime.date(2019, 6, 10)
    actual_date = next(workdate_iterator)
    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'


def test_assigneeworkdateiterator_with_personal_holidays_workday_overlap():
    holidays = [
        datetime.date(2019, 6, 4),  # tuesday
        datetime.date(2019, 6, 5),  # wednesday
        datetime.date(2019, 6, 6),  # thursday
    ]
    workdate_iterator = AssigneeWorkDateIterator(
        username='testuser',
        workdays=[
            'Thu',
            'Fri',
        ],
        personal_holidays=holidays,
        start_date=DATE_MONDAY
    )

    # friday
    expected_date = datetime.date(2019, 6, 7)
    actual_date = next(workdate_iterator)
    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'

    # the next thursday
    expected_date = datetime.date(2019, 6, 13)
    actual_date = next(workdate_iterator)
    assert actual_date == expected_date, f'actual({actual_date}) != expected({expected_date}'
