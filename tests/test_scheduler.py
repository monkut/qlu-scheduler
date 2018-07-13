"""
Test using the following command from the repository root:

    python -m pytest tests
"""
import datetime
import pytest
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday
from qlu.core import QluTaskScheduler, QluTask, QluTaskEstimates, QluMilestone, QluTaskNotAssigned
from qlu.utilities import PhantomUserAssignmentManager, AssigneeChooser


START_DATE = datetime.datetime(2017, 9, 10).date()


class TestBusinessCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday('test holiday 1', month=9, day=4),
        Holiday('test holiday 2', month=9, day=15),
        Holiday('test holiday 3', month=9, day=23),
    ]


HOLIDAY_CALENDAR = TestBusinessCalendar()

PERSONAL_HOLIDAYS = {
    'user-a': [datetime.date(2017, 10, 15)],
    'user-b': [datetime.date(2017, 10, 9)],
}

# Required Components for task scheduling
# (ABSOLUTE_PRIORITY, TASK_ID, [DEPENDS_ON, ..], (ESTIMATE_MIN, ESTIMATE_PROBABLE, ESTIMATE_MAX), [ASSIGNEE-A, ASSIGNEE-B], PROJECT, MILESTONE)

TEST_MILESTONES = [
    # NAME: (STARTDATETIME, ENDDATETIME)
    QluMilestone(
        'milestone-a',
        datetime.datetime(2017, 9, 15).date(),
        datetime.datetime(2017, 10, 20).date(),
    ),
    QluMilestone(
        'milestone-b',
        datetime.datetime(2017, 10, 3).date(),
        datetime.datetime(2017, 10, 19).date(),
    )
]


TEST_TASKS = {
    # prioritized tasks
    QluTask(1, 1, QluTaskEstimates(3, 5, 15), 'user-a', 'project-a', 'milestone-a', None),
    QluTask(2, 3, QluTaskEstimates(3, 5, 15), 'user-a', 'project-a', 'milestone-b', (1,)),
    QluTask(3, 2, QluTaskEstimates(3, 5, 15), 'user-b', 'project-a', 'milestone-a', None),
}

TEST_TASKS_NONE_ASSIGNED = {
    QluTask(1, 1, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
    QluTask(2, 3, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', (1,)),
    QluTask(3, 2, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
}


def test_qlutask_instaniation():
    e = QluTaskEstimates(3, 5, 15)
    assignee = 'u1'
    t = QluTask(1, 99, e, assignee, 'project-a', 'milestone-a', None)
    assert t.id == 1
    assert t.absolute_priority == 99
    assert t.depends_on is None
    assert t.estimates == e
    assert t.assignee == assignee
    assert t.project_id == 'project-a'
    assert t.milestone_id == 'milestone-a'


def test_scheduler():
    """
    Test basic scheduler
    :return:
    """
    PERSONAL_HOLIDAYS = {
        'user-a': [datetime.date(2017, 10, 15)],
        'user-b': [datetime.date(2017, 9, 18), datetime.date(2017, 10, 9)],
    }

    scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                                 holiday_calendar=HOLIDAY_CALENDAR,
                                 assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                 start_date=START_DATE)
    schedule = scheduler.schedule(tasks=TEST_TASKS)
    scheduled_tasks = list(schedule.tasks())
    assert len(scheduled_tasks) == len(TEST_TASKS)

    assert scheduled_tasks[0].id == 1
    assert scheduled_tasks[0].milestone_id == 'milestone-a'
    assert scheduled_tasks[0].start_date == datetime.date(2017, 9, 18)  # should be next Monday
    assert scheduled_tasks[0].end_date == datetime.date(2017, 9, 22)

    assert scheduled_tasks[1].milestone_id == 'milestone-a'
    assert scheduled_tasks[1].start_date == datetime.date(2017, 9, 19)  # not started until milestone starts
    assert scheduled_tasks[1].end_date == datetime.date(2017, 9, 25)

    assert scheduled_tasks[2].milestone_id == 'milestone-b'
    assert scheduled_tasks[2].start_date == datetime.date(2017, 10, 3)  # not started until milestone starts
    assert scheduled_tasks[2].end_date == datetime.date(2017, 10, 9)


def test_scheduler_montecarlo():
    """
    Test scheduler with montecarlo
    :return:
    """
    scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                                 holiday_calendar=HOLIDAY_CALENDAR,
                                 assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                 start_date=START_DATE)
    schedule = scheduler.schedule(tasks=TEST_TASKS, is_montecarlo=True)  # single calculation
    assert len(list(schedule.tasks())) == len(TEST_TASKS)

    milestone_distributions, milestone_predicted_completion_dates = scheduler.montecarlo(TEST_TASKS, trials=1000, q=90)
    assert milestone_distributions

    for milestone, predicted_completion_date in milestone_predicted_completion_dates.items():
        assert isinstance(predicted_completion_date, datetime.date)


def test_phantomuserassignementmanager_assignee_generation():
    phantom_user_count = 14
    pmgr = PhantomUserAssignmentManager(phantom_user_count)
    assert pmgr.usernames
    assert len(pmgr.usernames) == phantom_user_count


def test_phantomuserassignmentmanager_task_assignment():
    phantom_user_count = 3
    pmgr = PhantomUserAssignmentManager(phantom_user_count)
    assert len(pmgr.usernames) == phantom_user_count

    TEST_TASKS_NONE_ASSIGNED = {
        QluTask(1, 1, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
        QluTask(2, 3, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', (1,)),
        QluTask(3, 2, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
    }

    assigned_tasks = pmgr.assign(TEST_TASKS_NONE_ASSIGNED)
    assert list(assigned_tasks)
    assert all(t.assignee for t in assigned_tasks)


def test_assigneechooser_default():
    assignees = ['user1', 'user2', 'user3', 'user4']
    c = AssigneeChooser(assignees)

    picked = []
    for i in range(15):
        pick = c.choice()
        picked.append(pick)

    for assignee in assignees:
        assert assignee in picked


def test_phantom_user_assignment():
    # PhantomUserAssignmentManager.assign() will update the objects in place, so tests need to be refreshed
    TEST_TASKS_NONE_ASSIGNED = {
        QluTask(1, 1, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
        QluTask(2, 3, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', (1,)),
        QluTask(3, 2, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
    }

    with pytest.raises(QluTaskNotAssigned) as e:
        scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                                     holiday_calendar=HOLIDAY_CALENDAR,
                                     assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                     start_date=START_DATE)
        schedule = scheduler.schedule(tasks=TEST_TASKS_NONE_ASSIGNED)

    # assign phantom user
    phantom_user_count = 1
    pmgr = PhantomUserAssignmentManager(phantom_user_count)
    updated_tasks = pmgr.assign(TEST_TASKS_NONE_ASSIGNED)

    scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                                 holiday_calendar=HOLIDAY_CALENDAR,
                                 assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                 start_date=START_DATE)
    schedule = scheduler.schedule(tasks=updated_tasks)
    assert len(list(schedule.tasks())) == len(TEST_TASKS_NONE_ASSIGNED)

    assert len(schedule.assignees()) == 1
    expected_phantom_name = 'phantom-0'
    assert expected_phantom_name in schedule.assignees()
    max_single_phantom_date = schedule.final_date()
    phantom_user_count = 14
    pmgr = PhantomUserAssignmentManager(phantom_user_count)
    assert pmgr.usernames

    # PhantomUserAssignmentManager.assign() will update the objects in place, so tests need to be refreshed
    TEST_TASKS_NONE_ASSIGNED = {
        QluTask(1, 1, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
        QluTask(2, 3, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', (1,)),
        QluTask(3, 2, QluTaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a', None),
    }

    updated_tasks = list(pmgr.assign(TEST_TASKS_NONE_ASSIGNED))

    scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                                 holiday_calendar=HOLIDAY_CALENDAR,
                                 assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                 start_date=START_DATE)
    four_tasks_schedule = scheduler.schedule(tasks=updated_tasks)
    assert len(list(four_tasks_schedule.tasks())) == len(TEST_TASKS_NONE_ASSIGNED)
    max_four_phantom_date = four_tasks_schedule.final_date()

    # 14 phantoms randomly assigned *should* result in a earlier total completion date
    assert max_four_phantom_date < max_single_phantom_date
