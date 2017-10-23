import datetime
from qlu.adapters.github import GithubOrganizationProjectsAdaptor

PUBLIC_HOLIDAYS = (
    datetime.date(2017, 9, 23),
    datetime.date(2017, 9, 15),
    datetime.date(2017, 9, 4),
)
PERSONAL_HOLIDAYS = {
    'phantom-0': [datetime.date(2017, 10, 15)],
}


def test_github():
    """
    Tasks & Milestones are parsed from
    :return:
    """
    # TODO: updat to use dummy data json dumps
    adaptor = GithubOrganizationProjectsAdaptor('abeja-inc',
                                                ['New Test Project'],
                                                milestone_start_dates={},
                                                phantom_user_count=1,
                                                milestone_start_date_now=True)
    scheduler = adaptor.generate_task_scheduler()
    schedule = scheduler.schedule()
    assert len(adaptor._tasks) > 0
    assert schedule.tasks*()
    assert len(list(schedule.tasks())) == len(adaptor._tasks)