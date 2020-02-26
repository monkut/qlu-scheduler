import datetime
from unittest import TestCase

from qlu.core import QluTask, QluTaskError, QluTaskEstimates


class QluTaskTestCase(TestCase):
    def test_get_scheduled_dates(self):
        estimates = QluTaskEstimates(minimum=None, suggested=1, maximum=None)
        qlutask = QluTask(
            id="taskid-1",
            absolute_priority=1,
            estimates=estimates,
            assignee="sample-user",
            project_id="proj-1",
            milestone_id="milestone-1",
            depends_on=None,
        )
        with self.assertRaises(QluTaskError):
            list(qlutask.get_scheduled_dates())

        # add dates
        sample_date = datetime.date(2020, 1, 1)
        qlutask.scheduled_dates = [sample_date]

        dates = list(qlutask.get_scheduled_dates())
        self.assertTrue(dates)
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0], sample_date)
