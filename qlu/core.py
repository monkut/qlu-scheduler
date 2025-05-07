"""
Milestone defines when the task CAN start.
assignee schedule can define when the task IS started.
"""

import datetime
import logging
import warnings
from collections import Counter, defaultdict, namedtuple
from functools import lru_cache
from itertools import groupby
from operator import attrgetter, itemgetter
from typing import Any, Generator, Iterable, KeysView, Optional, Type

from numpy import percentile
from numpy.random import triangular
from toposort import toposort

try:
    from pandas.tseries.holiday import AbstractHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay
except ModuleNotFoundError:
    AbstractHolidayCalendar = None
    CustomBusinessDay = None

logger = logging.getLogger(__name__)

SATURDAY = 5
SUNDAY = 6
WEEKDAYS_OFF = (SATURDAY, SUNDAY)
WEEKDAY_IDENTIFIERS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

QluTaskEstimates = namedtuple("QluTaskEstimates", ("minimum", "suggested", "maximum"))

# 'project_id' is not needed here as QluTasks are linked to the specific project and to the QluMilestone
QluMilestone = namedtuple("QluMilestone", ("id", "start_date", "end_date"))


class MissingQluMilestone(Exception):
    """Exception for case where expected QluMilestone is not assigned to a QluTask."""

    pass


class MissingQluTaskEstimate(Exception):
    """Exception for case where an expected estimate value is missing"""

    pass


class QluTaskError(Exception):
    """Exception of general QluTask related errors."""

    pass


class QluMilestoneMissingDate(Exception):
    """Exception for case where expected 'date' is missing from a QluMilestone."""

    pass


class QluTaskNotAssigned(Exception):
    """Exception for case where QluTask does not have the assignee field populated."""

    pass


class AssigneeWorkDateIterator:
    """
    For a specific user, iterate through the available workdays (datetime.date()) for that user.
    Taking into account public_holidays and personal_holidays.
    """

    def __init__(
        self,
        username: str,
        holiday_calendar: Type[AbstractHolidayCalendar] = None,
        workdays: Optional[list[str]] = None,
        personal_holidays: Optional[list[datetime.date]] = None,
        start_date: Optional[datetime.date] = None,
    ):
        """

        :param username: assignee username
        :param holiday_calendar: Calendar defining public holidays
        :param workdays: assignee workdays in the week
            Format: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            Default=['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        :param personal_holidays: Holidays taken by the specific assignee (username)
        :param start_date: Date to start iterator at
        """
        self.username = username
        self.start_date = start_date if start_date else datetime.datetime.now(datetime.timezone.utc).date()

        # decrement in order to return initial start date so that the __next__ function can be easily reused
        self.current_date = self.start_date - datetime.timedelta(days=1)

        default_weekmask = "Mon Tue Wed Thu Fri"
        if workdays:
            # override the default weekmask
            if not all(weekday_id in WEEKDAY_IDENTIFIERS for weekday_id in workdays):
                raise ValueError(f"workdays must be in {WEEKDAY_IDENTIFIERS}, got: {workdays}")
            prepared_weekmask = " ".join(workdays)
        else:
            prepared_weekmask = default_weekmask

        # prepare business day offset
        # see: https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.tseries.offsets.CustomBusinessDay.html
        if CustomBusinessDay and AbstractHolidayCalendar:
            self.business_day_offset = CustomBusinessDay(weekmask=prepared_weekmask, calendar=holiday_calendar, holidays=personal_holidays)
        else:
            self.business_day_offset = None

    def __iter__(self):
        return self

    def __next__(self) -> datetime.date:
        if self.business_day_offset:
            self.current_date += self.business_day_offset
        if hasattr(self.current_date, "to_pydatetime"):
            self.current_date = self.current_date.to_pydatetime().date()
        else:
            assert isinstance(self.current_date, datetime.date)
            self.current_date += self.current_date

        return self.current_date


class QluTask:

    _field_order = ("id", "absolute_priority", "estimates", "assignee", "project_id", "milestone_id", "depends_on")

    def __init__(
        self,
        id: Any,
        absolute_priority: int,
        estimates: QluTaskEstimates,
        assignee: str,
        project_id: str,
        milestone_id: str,
        depends_on: tuple[int] = None,
    ):
        self.id = id
        self.absolute_priority = absolute_priority
        if not isinstance(estimates, QluTaskEstimates):
            raise ValueError(f"Expected (QluTaskEstimates) object, got: {estimates} {type(estimates)}")
        self.estimates = estimates
        self.assignee = assignee
        self.project_id = project_id
        if milestone_id is None:
            raise ValueError('Required "milestone_id" not defined!')
        self.milestone_id = milestone_id
        self.depends_on = depends_on
        self.scheduled_dates = []
        self._iter_pos = 0

    @property
    def start_date(self) -> Optional[datetime.date]:
        """
        :return: Scheduled start date of the Task.
        """
        return self.scheduled_dates[0] if self.scheduled_dates else None

    @property
    def end_date(self) -> Optional[datetime.date]:
        """
        :return: Scheduled end date of the Task.
        """
        return self.scheduled_dates[-1] if self.scheduled_dates else None

    @property
    def is_scheduled(self) -> bool:
        """
        :return: Signify if the Task is scheduled.
        """
        return True if self.scheduled_dates else False

    def get_scheduled_dates(self) -> Generator[datetime.date, None, None]:
        if not self.scheduled_dates:
            raise QluTaskError("QluTask not scheduled: Populated when scheduled via QluTaskScheduler.schedule(Iterable[QluTask])")
        for d in self.scheduled_dates:
            yield d

    def __iter__(self):
        self._iter_pos = 0
        return self

    def __next__(self):
        element_count = len(self._field_order)
        if self._iter_pos >= element_count:
            raise StopIteration
        element = self[self._iter_pos]
        self._iter_pos += 1
        return element

    def __getitem__(self, index: int) -> Any:
        fieldname = self._field_order[index]
        return getattr(self, fieldname)

    def __str__(self) -> str:
        return "QluTask(id={}, absolute_priority={}, project_id={}, milestone_id={}, assignee={})".format(
            self.id, self.absolute_priority, self.project_id, self.milestone_id, self.assignee
        )

    def __repr__(self) -> str:
        return self.__str__()


class QluSchedule:
    """
    Result Schedule object of QluTaskScheduler call
    """

    def __init__(self, scheduled_tasks: Iterable[QluTask], assignee_tasks: dict[Any, list[QluTask]]):
        """
        :param scheduled_tasks: All tasks
        :param assignee_tasks: Assignee Keyed task lists
        """
        assert all(t.is_scheduled for t in scheduled_tasks)  # expect that all tasks are scheduled
        self._scheduled_tasks = scheduled_tasks
        self._assignee_keyed_tasks = assignee_tasks

    def milestone_tasks(self) -> Generator:
        """
        Return

        :return:
            .. code:: python

                (QLUMILESTONE_ID, [QLUTASK, ]

        """
        milestone_id_sorted = sorted(self._scheduled_tasks, key=attrgetter("milestone_id"))
        for milestone_id, tasks in groupby(milestone_id_sorted, attrgetter("milestone_id")):
            yield milestone_id, list(tasks)

    def tasks(self, assignee: str = None) -> list[QluTask]:
        """
        Return scheduled tasks ordered_by and finish date.

        :param assignee: if given, resulting task list will be filtered for the given assignee
        """
        all_tasks = []
        for assigned_user, tasks in self._assignee_keyed_tasks.items():
            if assignee and assigned_user != assignee:
                continue
            all_tasks.extend(tasks)
        return sorted(all_tasks, key=attrgetter("end_date"))

    def assignees(self) -> KeysView:
        """
        :return: All assignees scheduled with tasks.
        """
        return self._assignee_keyed_tasks.keys()

    @lru_cache(maxsize=25)
    def final_task(self, assignee: str = None) -> QluTask:
        """
        :param assignee: assignee to get task for.
        :return: last task assigneed to given assignee.
        """
        tasks = self.tasks(assignee)
        final_task = max(tasks, key=attrgetter("end_date"))
        return final_task

    def final_date(self, assignee: str = None) -> datetime.date:
        """
        :param assignee: assignee to get task final date for.
        :return: last assigned work data for assignee.
        """
        task = self.final_task(assignee)
        return task.end_date


class QluTaskScheduler:
    """Methods to schedule tasks given a set of milestones, tasks and holidays."""

    def __init__(
        self,
        milestones: Iterable[QluMilestone],
        holiday_calendar: Type[AbstractHolidayCalendar] = None,
        assignee_workdays: Optional[dict[str, list[str]]] = None,
        assignee_personal_holidays: Optional[dict[str, Iterable[datetime.date]]] = None,
        start_date: Optional[datetime.date] = None,
    ):
        """
        :param milestones: list of Milestone objects
        :param holiday_calendar: Calendar object for determining work days
        :param assignee_workdays: Week workdays for given assignee.
            In format:
                {'username': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] }
            If not given, default to ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        :param assignee_personal_holidays: (dict) of personal holidays (datetime.date()) keyed by task username
        :param start_date: (datetime.date) Start date of scheduling (if not given current UTC value used)
        """
        # check that milestones contain expected start, end dates
        for m in milestones:
            if not m.start_date or not m.end_date:
                raise QluMilestoneMissingDate("Milestone must have BOTH start_date and end_date defined: {}".format(m))
        self.id_keyed_milestones = {m.id: m for m in milestones}
        self.holiday_calendar = holiday_calendar
        self.assignee_workdays = assignee_workdays
        self.assignee_personal_holidays = assignee_personal_holidays
        self._start_date = start_date

    def montecarlo(self, tasks: Iterable[QluTask], trials: int = 5000, q: int = 90) -> tuple[dict[Any, Counter], dict[str, datetime.date]]:
        """
        Run montecarlo simulation for the number of trials specified.

        :param tasks: list of QluTask objects to run montecarlo scheduling on
        :param trials: number of trials
        :param q: 0-100, percentile at which to retrieve predicted completion date
        """
        milestone_completion_distribution = defaultdict(Counter)
        milestone_completion_ordinals = defaultdict(list)
        for trial in range(trials):
            schedule = self.schedule(tasks, is_montecarlo=True)
            for milestone, milestone_tasks in schedule.milestone_tasks():
                milestone_completion_date = max(task.end_date for task in milestone_tasks)
                milestone_completion_ordinals[milestone].append(milestone_completion_date.toordinal())
                milestone_completion_distribution[milestone][milestone_completion_date.isoformat()] += 1

        milestone_date_at_percentile = {}
        for milestone, completion_ordinals in milestone_completion_ordinals.items():
            ordinal_at_percentile = percentile(completion_ordinals, q)
            date_at_percentile = datetime.datetime.fromordinal(int(ordinal_at_percentile))
            milestone_date_at_percentile[milestone] = date_at_percentile
        return milestone_completion_distribution, milestone_date_at_percentile

    def _check_milestones(self, id_keyed_tasks: dict[Any, QluTask]) -> None:
        """
        Check that a QluMilestone is assigned to all QluTasks as expected.
        If not found, raises MissingMilestone.

        :param id_keyed_tasks:
        :raises: MissingMilestone
        """
        # perform milestone check
        task_milestone_ids = [t.milestone_id for t in id_keyed_tasks.values() if t.milestone_id]
        for milestone_id in task_milestone_ids:
            if milestone_id not in self.id_keyed_milestones:
                raise MissingQluMilestone("Required QluMilestone definition missing: {}".format(milestone_id))

    def _prepare_assignee_workday_iterators(self, unique_assignees: set[str]) -> dict[Any, Iterable]:
        """
        Create the workday iterators for all assignees.

        :param unique_assignees: all assignee names in given QluTasks
        :return:
            Workday iterator for each assignee taking into account public holidays defined in calendar,
            and individual personal_holidays.

            .. code::

                { 'ASSIGNEE_NAME': WORKDAY_ITERATOR, }

        """
        # build assignee iterators
        assignees_date_iterators = {}
        for unique_assignee in unique_assignees:
            if self.assignee_personal_holidays:
                personal_holidays = self.assignee_personal_holidays.get(unique_assignee, [])
                if unique_assignee not in self.assignee_personal_holidays:
                    warnings.warn("personal_holiday date list not given for: {}".format(unique_assignee))
            else:
                personal_holidays = []
                warnings.warn("personal_holidays NOT set!  Assignee holidays will NOT be taken into account!")

            workdays = None
            if self.assignee_workdays:
                raw_workdays = self.assignee_workdays.get(unique_assignee, None)
                if raw_workdays:
                    # clean and normalize
                    cleaned_workdays = [day.lower().capitalize()[:3] for day in raw_workdays]
                    if not all(cleaned_day in WEEKDAY_IDENTIFIERS for cleaned_day in cleaned_workdays):
                        raise ValueError(f"Invalid workday given, must be in {WEEKDAY_IDENTIFIERS}, got: {raw_workdays}")
                    logger.debug(f"{unique_assignee}.workdays={cleaned_workdays}")
                    workdays = cleaned_workdays

            # build work date iterator
            assignees_date_iterator = AssigneeWorkDateIterator(
                unique_assignee, self.holiday_calendar, workdays, personal_holidays, start_date=self._start_date
            )
            assignees_date_iterators[unique_assignee] = assignees_date_iterator
        return assignees_date_iterators

    def _prepare_task_dependency_graph(self, dependant_tasks: dict[Any, QluTask]) -> list:
        """
        Process task dependencies as defined in the QluTask.depends_on value

        :param dependant_tasks: QluTasks with task dependencies.
        :return: dependency graph

            .. code::

                [{TOP_LEVEL_TASK_ID, TOP_LEVEL_TASK_ID, }, {NEXT_LEVEL_TASK_ID}, ]

        """
        # create toposort compatible structure for tasks with dependencies
        dependencies = {}
        for task_id, components in dependant_tasks.items():
            dependant_task_ids = set(components.depends_on)
            dependencies[task_id] = dependant_task_ids

        # get dependency graph
        dependency_graph = list(toposort(dependencies))
        return dependency_graph

    def _schedule_tasks(self, id_keyed_tasks, dependency_graph, unique_assignees, is_montecarlo=False):
        """
        Schedule QluTasks to assignees.

        :param id_keyed_tasks:
        :param dependency_graph:
        :param unique_assignees:
        :param is_montecarlo:
        :return:
        """
        assignees_date_iterators = self._prepare_assignee_workday_iterators(unique_assignees)

        # group tasks by assignee
        # --> Tasks in each group are independent, and can be run in parallel (but user specific)
        all_assignee_tasks = defaultdict(list)
        for task_group_index, task_group in enumerate(dependency_graph):

            # collect task information in current group
            task_details = {task_id: id_keyed_tasks[task_id] for task_id in task_group}
            sorted_task_detail_values = sorted(task_details.values(), key=attrgetter("assignee"))

            # group tasks by assignees
            # --> if more than 1 assignee, select 1, and issue warning
            for assignee, assignee_tasks in groupby(sorted_task_detail_values, attrgetter("assignee")):

                # process assignee tasks
                # --> sort by milestone.enddate, priority, and schedule
                temp_priority_sorted_assignee_tasks = []
                for temp_assignee_task in assignee_tasks:
                    milestone_id = temp_assignee_task.milestone_id
                    _, milestone_start_date, milestone_end_date = self.id_keyed_milestones[milestone_id]
                    key = (milestone_end_date, temp_assignee_task.absolute_priority)
                    temp_priority_sorted_assignee_tasks.append((key, temp_assignee_task))
                priority_sorted_assignee_tasks = [t for key, t in sorted(temp_priority_sorted_assignee_tasks, key=itemgetter(0))]

                assignee_task_count = len(priority_sorted_assignee_tasks)
                assignee_scheduled_task_count = 0
                looped_work_date = None
                while True:
                    for task in priority_sorted_assignee_tasks:
                        task_id = task.id
                        milestone_id = task.milestone_id
                        _, milestone_start_date, milestone_end_date = self.id_keyed_milestones[milestone_id]
                        min_estimate, main_estimate, max_estimate = task.estimates

                        estimate = main_estimate
                        if is_montecarlo:
                            # get random number using triangular distribution
                            # -- yes, this would be more efficient if we got a bunch here when running montecarlo,
                            # -- but, it's difficult to do when tasks are inter-dependant.
                            estimate = int(triangular(min_estimate, main_estimate, max_estimate, size=1)[0])
                        if not estimate or estimate <= 0:
                            raise MissingQluTaskEstimate(f"{task} has an invalid estimate: estimate={estimate}")

                        # Check milestone has started before scheduling with assignee
                        if assignees_date_iterators[assignee].current_date >= milestone_start_date:
                            if not task.is_scheduled:  # make sure it's added only once
                                # add to all tasks
                                all_assignee_tasks[assignee].append(task)

                                # schedule task for user
                                for day in range(estimate):
                                    if looped_work_date:
                                        work_date = looped_work_date
                                        looped_work_date = None
                                    else:
                                        work_date = next(assignees_date_iterators[assignee])
                                    id_keyed_tasks[task_id].scheduled_dates.append(work_date)
                                assignee_scheduled_task_count += 1

                        else:
                            warnings.warn(f"NOTICE -- QluTask({task_id}) QluMilestone({milestone_id}) not yet started!")
                    # single loop complete,
                    # --> check if fully scheduled, if not increment user dates
                    if assignee_scheduled_task_count < assignee_task_count:
                        # increment
                        looped_work_date = next(assignees_date_iterators[assignee])
                    elif all(t.is_scheduled for t in priority_sorted_assignee_tasks):
                        break  # All tasks are scheduled
                    else:
                        unscheduled_tasks = [t for t in priority_sorted_assignee_tasks if not t.is_scheduled]
                        warnings.warn(f"Not all tasks are scheduled, re-evaluating tasks: {unscheduled_tasks}")
        return id_keyed_tasks, all_assignee_tasks

    def schedule(self, tasks: Iterable[QluTask], is_montecarlo: bool = False) -> QluSchedule:
        """
        Schedule tasks given on instantiation.

        :param tasks: list of QluTasks
        :param is_montecarlo: If True, random value selected using triangular distribution
        """
        if not tasks:
            raise ValueError("Expected argument value not valid (tasks): {}".format(tasks))
        unique_assignees = set()
        id_keyed_tasks = {}
        for t in tasks:
            # clear scheduled dates
            if t.scheduled_dates:
                t.scheduled_dates = []
            id_keyed_tasks[t.id] = t

        self._check_milestones(id_keyed_tasks)

        # filter tasks to dependant and non-dependant
        dependant_tasks = {}
        non_dependant_tasks = {}
        for task_id, task_object in id_keyed_tasks.items():
            if task_object.depends_on:
                dependant_tasks[task_id] = task_object
            else:
                non_dependant_tasks[task_id] = task_object
            if task_object.assignee:
                unique_assignees.add(task_object.assignee)

        if not unique_assignees:
            raise QluTaskNotAssigned(
                "QluTasks must have an assignee value! "
                ">Use qlu.utilities.PhantomUserAssignmentManager to generate and assign Users for schedule prediction"
            )

        dependency_graph = self._prepare_task_dependency_graph(dependant_tasks)

        # update dependency_graph with non_dependant tasks
        if dependency_graph:
            # include non_dependant tasks to existing first group
            task_group = dependency_graph[0]
            for task_id in non_dependant_tasks.keys():
                task_group.add(task_id)
        else:
            dependency_graph = [{task_id for task_id in non_dependant_tasks.keys()}]

        id_keyed_tasks, all_assignee_tasks = self._schedule_tasks(id_keyed_tasks, dependency_graph, unique_assignees, is_montecarlo)

        # attach scheduled dates to task objects
        scheduled_tasks = id_keyed_tasks.values()  # find is_schedule false
        for st in scheduled_tasks:
            if not st.is_scheduled:
                print(st)
        qlu_schedule = QluSchedule(scheduled_tasks, all_assignee_tasks)
        return qlu_schedule
