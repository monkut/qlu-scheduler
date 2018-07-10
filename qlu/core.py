"""
Milestone defines when the task CAN start
assignee schedule can define when the task IS started.
"""
import datetime
import warnings
import random
from typing import Any, Dict, Tuple, List, Generator, Optional, KeysView, Iterable
from functools import lru_cache
from itertools import groupby
from operator import attrgetter
from collections import defaultdict, namedtuple, Counter
from toposort import toposort
from numpy.random import triangular
from numpy import percentile


SATURDAY = 5
SUNDAY = 6
WEEKDAYS_OFF = (SATURDAY, SUNDAY)

QluTaskEstimates = namedtuple('QluTaskEstimates', ('minimum', 'suggested', 'maximum'))
QluMilestone = namedtuple('QluMilestone', ('id', 'start_date', 'end_date'))


class MissingMilestone(Exception):
    pass


class MilestoneMissingDate(Exception):
    pass


class TaskNotAssigned(Exception):
    pass


class AssigneeWorkDateIterator:
    """
    For a specific user, iterate through the available workdays (datetime.date()) for that user.
    Taking into account public_holidays and personal_holidays
    """

    def __init__(self, username: str, public_holidays: Iterable[datetime.date]=None, personal_holidays: List[datetime.date]=None, weekdays_off: Tuple[int, ...]=WEEKDAYS_OFF, start_date: Optional[datetime.date]=None):
        self.username = username
        self.public_holidays = public_holidays if public_holidays is not None else []
        self.personal_holidays = personal_holidays if personal_holidays is not None else []
        self.combined_holidays = tuple(list(self.public_holidays) + list(self.personal_holidays))
        self.weekdays_off = weekdays_off
        self.start_date = start_date if start_date else datetime.datetime.utcnow().date()

        # decrement in order to return initial start date so that the __next__ function can be easily reused
        self.current_date = self.start_date - datetime.timedelta(days=1)

    def __iter__(self):
        return self

    def __next__(self) -> datetime.date:
        self.current_date += datetime.timedelta(days=1)
        while self.current_date.weekday() in self.weekdays_off or self.current_date in self.combined_holidays:
            self.current_date += datetime.timedelta(days=1)
        return self.current_date


class QluTask:
    
    _field_order = (
                'id',
                'absolute_priority',
                'depends_on',
                'estimates',
                'assignee',
                'project_id',
                'milestone_id',
            )    
    
    def __init__(self, id: Any, absolute_priority, estimates, assignee, project_id, milestone_id, depends_on: str=None):
        self.id = id
        self.absolute_priority = absolute_priority
        assert isinstance(estimates, QluTaskEstimates)
        self.estimates = estimates
        self.assignee = assignee
        self.project_id = project_id
        self.milestone_id = milestone_id
        self.depends_on = depends_on
        self.scheduled_dates = []
        self._iter_pos = 0

    @property
    def start_date(self) -> Optional[datetime.date]:
        return self.scheduled_dates[0] if self.scheduled_dates else None

    @property
    def end_date(self) -> Optional[datetime.date]:
        return self.scheduled_dates[-1] if self.scheduled_dates else None

    @property
    def is_scheduled(self) -> bool:
        result = False
        if self.scheduled_dates:
            result = True
        return result

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
        return 'QluTask(id={}, project_id={}, milestone_id={}, assignee={})'.format(self.id,
                                                                                    self.project_id,
                                                                                    self.milestone_id,
                                                                                    self.assignee)

    def __repr__(self) -> str:
        return self.__str__()


class QluSchedule:
    """
    Result Schedule object of TaskScheduler call
    """

    def __init__(self, scheduled_tasks: Iterable[QluTask], assignee_tasks: Dict[Any, List[QluTask]]):
        assert all(t.is_scheduled for t in scheduled_tasks)  # expect that all tasks are scheduled
        self._scheduled_tasks = scheduled_tasks
        self._assignee_keyed_tasks = assignee_tasks

    def milestone_tasks(self) -> Generator:
        milestone_id_sorted = sorted(self._scheduled_tasks, key=attrgetter('milestone_id'))
        for milestone_id, tasks in groupby(milestone_id_sorted, attrgetter('milestone_id')):
            yield milestone_id, list(tasks)

    def tasks(self, assignee: str=None) -> List[QluTask]:
        """
        Return scheduled tasks ordered_by and finish date

        :param assignee: if given, resulting task list will be filtered for the given assignee
        """
        all_tasks = []
        for assigned_user, tasks in self._assignee_keyed_tasks.items():
            if assignee and assigned_user != assignee:
                continue
            all_tasks.extend(tasks)
        return sorted(all_tasks, key=attrgetter('end_date'))

    def assignees(self) -> KeysView:
        return self._assignee_keyed_tasks.keys()

    @lru_cache(maxsize=25)
    def final_task(self, assignee: str=None) -> QluTask:
        tasks = self.tasks(assignee)
        final_task = max(tasks, key=attrgetter('end_date'))
        return final_task

    def final_date(self, assignee: str=None) -> datetime.date:
        task = self.final_task(assignee)
        return task.end_date


class QluTaskScheduler:

    def __init__(self, milestones: Iterable[QluMilestone], public_holidays: Iterable[datetime.date]=None, assignee_personal_holidays: Dict[str, List[datetime.date]]=None, phantom_user_count: int=0, start_date: Optional[datetime.date]=None):
        """
        :param milestones: List of Milestone objects
        :param assignee_personal_holidays: (dict) of personal holidays (datetime.date()) keyed by task username
        :param phantom_user_count: (int) Number of 'phantom' users to assign unassigned tasks to
            NOTE: Intended to help with determining how many Resources are needed for the project.
        :param start_date: (datetime.date) Start date of scheduling (if not given current UTC value used)
        """
        # check that milestones contain expected start, end dates
        for m in milestones:
            if not m.start_date or not m.end_date:
                raise MilestoneMissingDate('Milestone must have BOTH start_date and end_date defined: {}'.format(m))
        self.id_keyed_milestones = {m.id: m for m in milestones}
        self.public_holidays = public_holidays
        self.assignee_personal_holidays = assignee_personal_holidays
        self.phantom_user_count = phantom_user_count
        self._start_date = start_date

    def montecarlo(self, tasks: Iterable[QluTask], trials: int=5000, q: int=90) -> Tuple[Dict[Any, Counter], Dict[str, datetime.date]]:
        """
        Run montecarlo simulation for the number of trials specified
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

    def schedule(self, tasks: Iterable[QluTask], is_montecarlo: bool=False) -> QluSchedule:
        """
        Schedule tasks given on instantiation
        :param tasks: List of QluTasks
        :param is_montecarlo: If True, random value selected using triangular distribution
        """
        unique_assignees = set()
        id_keyed_tasks = {}
        for t in tasks:
            # clear scheduled dates
            if t.scheduled_dates:
                t.scheduled_dates = []
            id_keyed_tasks[t.id] = t

        # perform milestone check
        task_milestone_ids = [t.milestone_id for t in id_keyed_tasks.values() if t.milestone_id]
        for milestone_id in task_milestone_ids:
            if milestone_id not in self.id_keyed_milestones:
                raise MissingMilestone('Required Milestone definition missing for: {}'.format(milestone_id))

        # add phantom users if defined
        phantom_usernames = []  # used for assignment
        if self.phantom_user_count:
            for i in range(self.phantom_user_count):
                name = 'phantom-{}'.format(i)
                unique_assignees.add(name)  # used to assure AssigneeWorkDateIterator object is created for phantom user
                phantom_usernames.append(name)

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
            elif phantom_usernames:
                # randomly assign
                assignee = random.choice(phantom_usernames)
                warnings.warn('Assigning Phantom User: {}'.format(assignee))
                # Task(2, 3, None, TaskEstimates(3, 5, 15), ('user-b', ), 'project-a', 'milestone-a'),
                assignee_index = 4
                new_task_attributes = []
                for index, existing_value in enumerate(task_object):
                    if index == assignee_index:
                        new_task_attributes.append(assignee)
                    else:
                        new_task_attributes.append(existing_value)
                # update task
                new_task = QluTask(*new_task_attributes)
                id_keyed_tasks[task_id] = new_task

        if not unique_assignees and not self.phantom_user_count:
            msg = ('Tasks not assigned and phantom_user_count == {}! '
                   '(TaskScheduler(..., phantom_user_count=1) can be set to a positive integer to simulate assignments)').format(self.phantom_user_count)

            raise TaskNotAssigned(msg)

        # build assignee iterators
        assignees_date_iterators = {}
        for unique_assignee in unique_assignees:
            if self.assignee_personal_holidays:
                personal_holidays = self.assignee_personal_holidays.get(unique_assignee, [])
                if unique_assignee not in self.assignee_personal_holidays:
                    warnings.warn('personal_holiday date list not given for: {}'.format(unique_assignee))
            else:
                personal_holidays = []
                warnings.warn('personal_holidays NOT set!  Assignee holidays will NOT be taken into account!')

            # build work date iterator
            assignees_date_iterator = AssigneeWorkDateIterator(unique_assignee,
                                                               self.public_holidays,
                                                               personal_holidays,
                                                               start_date=self._start_date)
            assignees_date_iterators[unique_assignee] = assignees_date_iterator

        # create toposort compatible structure for tasks with dependencies
        dependencies = {}
        for task_id, components in dependant_tasks.items():
            dependant_task_ids = set(components.depends_on)
            dependencies[task_id] = dependant_task_ids

        # get dependency graph
        dependency_graph = list(toposort(dependencies))

        # update with non_dependant tasks
        if dependency_graph:
            # include non_dependant tasks to existing first group
            task_group = dependency_graph[0]
            for task_id in non_dependant_tasks.keys():
                task_group.add(task_id)
        else:
            dependency_graph = [{task_id for task_id in non_dependant_tasks.keys()}]
        # group tasks by assignee
        # --> Tasks in each group are independent, and can be run in parallel (but user specific)
        all_assignee_tasks = defaultdict(list)
        for task_group_index, task_group in enumerate(dependency_graph):

            # collect task information in current group
            task_details = {task_id: id_keyed_tasks[task_id] for task_id in task_group}
            sorted_task_detail_values = sorted(task_details.values(), key=attrgetter('assignee'))

            # group tasks by assignees
            # --> if more than 1 assignee, select 1, and issue warning
            for assignee, assignee_tasks in groupby(sorted_task_detail_values, attrgetter('assignee')):
                # process assignee tasks
                # --> sort by priority, and schedule
                priority_sorted = sorted(assignee_tasks, key=attrgetter('absolute_priority'))
                assignee_task_count = len(priority_sorted)

                assignee_scheduled_task_count = 0
                looped_work_date = None
                while True:
                    for task in priority_sorted:
                        task_id = task.id
                        milestone_id = task.milestone_id
                        _, milestone_start_date, milestone_end_date = self.id_keyed_milestones[milestone_id]
                        min_estimate, main_estimate, max_estimate = task.estimates
                        if is_montecarlo:
                            # get random number using triangular distribution
                            # -- yes, this would be more efficient if we got a bunch here when running montecarlo,
                            # -- but, it's difficult to do when tasks are inter-dependant.
                            estimate = int(triangular(min_estimate, main_estimate, max_estimate, size=1)[0])
                        else:
                            estimate = main_estimate

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
                            warnings.warn('NOTICE -- QluTask({}) QluMilestone({}) not yet started!'.format(task_id,
                                                                                                           milestone_id))
                    # single loop complete,
                    # --> check if fully scheduled, if not increment user dates
                    if assignee_scheduled_task_count < assignee_task_count:
                        # increment
                        looped_work_date = next(assignees_date_iterators[assignee])
                    else:
                        break  # All tasks are scheduled

        # attach scheduled dates to task objects
        scheduled_tasks = id_keyed_tasks.values()
        qlu_schedule = QluSchedule(scheduled_tasks, all_assignee_tasks)
        return qlu_schedule
