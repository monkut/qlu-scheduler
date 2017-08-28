import datetime
from qlu.core import TaskScheduler, Task, TaskEstimates, Milestone

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
    Task(1, 1, None, TaskEstimates(3, 9, 15), ('user-a', ), 'project-a', 'milestone-a'),
    Task(3, 2, (1,), TaskEstimates(3, 9, 15), ('user-a', ), 'project-a', 'milestone-b'),
    Task(2, 3, None, TaskEstimates(3, 9, 15), ('user-b', ), 'project-a', 'milestone-a'),
}


def test_scheduler():
    # tasks, milestones, public_holidays, assignee_personal_holidays

    scheduler = TaskScheduler(tasks=TEST_TASKS,
                              milestones=TEST_MILESTONES,
                              public_holidays=PUBLIC_HOLIDAYS,
                              assignee_personal_holidays=PERSONAL_HOLIDAYS)
    result = scheduler.schedule()
    assert result
    print(result)
