"""
Test using the following command from the repository root:

    python -m pytest tests
"""
import datetime
import pytest
from qlu.core import TaskScheduler, Task, TaskEstimates, Milestone, TaskNotAssigned


START_DATE = datetime.datetime(2017, 9, 10).date()

PUBLIC_HOLIDAYS = (
    datetime.date(2017, 9, 23),
    datetime.date(2017, 9, 15),
    datetime.date(2017, 9, 4),
)
PERSONAL_HOLIDAYS = {
    'user-a': [datetime.date(2017, 10, 15)],
    'user-b': [datetime.date(2017, 10, 9)],
}

# Required Components for task scheduling
# (ABSOLUTE_PRIORITY, TASK_ID, [DEPENDS_ON, ..], (ESTIMATE_MIN, ESTIMATE_PROBABLE, ESTIMATE_MAX), [ASSIGNEE-A, ASSIGNEE-B], PROJECT, MILESTONE)

TEST_MILESTONES = [
    # NAME: (STARTDATETIME, ENDDATETIME)
    Milestone(
        'milestone-a',
        datetime.datetime(2017, 9, 15).date(),
        datetime.datetime(2017, 10, 20).date(),
    ),
    Milestone(
        'milestone-b',
        datetime.datetime(2017, 10, 3).date(),
        datetime.datetime(2017, 10, 19).date(),
    )
]


TEST_TASKS = {
    # prioritized tasks
    Task(1, 1, None, TaskEstimates(3, 5, 15), ('user-a', ), 'project-a', 'milestone-a'),
    Task(3, 2, (1,), TaskEstimates(3, 5, 15), ('user-a', ), 'project-a', 'milestone-b'),
    Task(2, 3, None, TaskEstimates(3, 5, 15), ('user-b', ), 'project-a', 'milestone-a'),
}

TEST_TASKS_NONE_ASSIGNED = {
    Task(1, 1, None, TaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a'),
    Task(3, 2, (1,), TaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a'),
    Task(2, 3, None, TaskEstimates(3, 5, 15), None, 'project-a', 'milestone-a'),
}


def test_scheduler():
    """
    Test basic scheduler
    :return:
    """
    scheduler = TaskScheduler(tasks=TEST_TASKS,
                              milestones=TEST_MILESTONES,
                              public_holidays=PUBLIC_HOLIDAYS,
                              assignee_personal_holidays=PERSONAL_HOLIDAYS,
                              start_date=START_DATE)
    scheduled_tasks, assignee_tasks = scheduler.schedule()
    assert len(scheduled_tasks) == len(TEST_TASKS)
    assert scheduled_tasks[1][0] == datetime.date(2017, 9, 18)  # should be next Monday
    assert scheduled_tasks[1][-1] == datetime.date(2017, 9, 22)
    assert scheduled_tasks[2][0] == datetime.date(2017, 10, 3)  # not started until milestone starts
    assert scheduled_tasks[2][-1] == datetime.date(2017, 10, 9)
    assert scheduled_tasks[3][0] == datetime.date(2017, 9, 18)  # not started until milestone starts
    assert scheduled_tasks[3][-1] == datetime.date(2017, 9, 22)


def test_scheduler_montecarlo():
    """
    Test scheduler with montecarlo
    :return:
    """
    scheduler = TaskScheduler(tasks=TEST_TASKS,
                              milestones=TEST_MILESTONES,
                              public_holidays=PUBLIC_HOLIDAYS,
                              assignee_personal_holidays=PERSONAL_HOLIDAYS,
                              start_date=START_DATE)
    scheduled_tasks, assignee_tasks = scheduler.schedule(is_montecarlo=True)  # single calculation
    assert len(scheduled_tasks) == len(TEST_TASKS)

    milestone_distributions, milestone_predicted_completion_dates = scheduler.montecarlo(1000, q=90)
    assert milestone_distributions

    for milestone, predicted_completion_date in milestone_predicted_completion_dates.items():
        assert isinstance(predicted_completion_date, datetime.date)


def test_phantom_user_assignment():
    with pytest.raises(TaskNotAssigned) as e:
        scheduler = TaskScheduler(tasks=TEST_TASKS_NONE_ASSIGNED,
                                  milestones=TEST_MILESTONES,
                                  public_holidays=PUBLIC_HOLIDAYS,
                                  assignee_personal_holidays=PERSONAL_HOLIDAYS,
                                  start_date=START_DATE)
        scheduled_tasks, assignee_tasks = scheduler.schedule()

    # assign phantom user
    scheduler = TaskScheduler(tasks=TEST_TASKS_NONE_ASSIGNED,
                              milestones=TEST_MILESTONES,
                              public_holidays=PUBLIC_HOLIDAYS,
                              assignee_personal_holidays=PERSONAL_HOLIDAYS,
                              phantom_user_count=1,
                              start_date=START_DATE)
    scheduled_tasks, assignee_tasks = scheduler.schedule()
    assert len(scheduled_tasks) == len(TEST_TASKS_NONE_ASSIGNED)

    assert len(assignee_tasks.keys()) == 1
    expected_phantom_name = 'phantom-0'
    assert expected_phantom_name in assignee_tasks.keys()
    max_single_phantom_date = max(sum(scheduled_tasks.values(), []))

    scheduler = TaskScheduler(tasks=TEST_TASKS_NONE_ASSIGNED,
                              milestones=TEST_MILESTONES,
                              public_holidays=PUBLIC_HOLIDAYS,
                              assignee_personal_holidays=PERSONAL_HOLIDAYS,
                              phantom_user_count=14,
                              start_date=START_DATE)
    scheduled_tasks_four, assignee_tasks = scheduler.schedule()
    assert len(scheduled_tasks) == len(TEST_TASKS_NONE_ASSIGNED)
    max_four_phantom_date = max(sum(scheduled_tasks_four.values(), []))
    # 14 phantoms randomly assigned *should* result in a earlier total completion date
    assert max_four_phantom_date < max_single_phantom_date
