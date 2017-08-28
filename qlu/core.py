"""
Milestone defines when the task CAN start
assignee schedule can define when the
"""
import datetime
import warnings
from itertools import groupby
from operator import attrgetter
from collections import defaultdict, namedtuple
from toposort import toposort
from numpy.random import triangular


SATURDAY = 5
SUNDAY = 6
WEEKDAYS_OFF = (SATURDAY, SUNDAY)


TaskEstimates = namedtuple('TaskEstimates', ('minimum', 'suggested', 'maximum'))
Task = namedtuple('Task', (
    'absolute_priority',
    'id',
    'depends_on',
    'estimates',
    'assignees',
    'project',
    'milestone',
))
Milestone = namedtuple('Milestone', ('name', 'start_date', 'end_date'))


class MissingMilestone(Exception):
    pass


class TaskNotAssigned(Exception):
    pass


def by_assignee(data):
    """
    Given the detailed task data, return the assignee to the task.
    Used for keying in the groupby function.
    """
    # return key to sort by
    assignee_index = 4
    assignees = data[assignee_index]
    # sort to make result same on each instance
    if assignees:
        if len(assignees) > 1:
            warnings.warn('More than 1 assignee, selecting the first, sorted alphanumerically')
            assignee = sorted(assignees)[0]
        else:
            assignee = assignees[0]
    else:
        # pick and auto assign
        raise TaskNotAssigned('no assignee for task: Task({data.id})')
    return assignee


class AssigneeWorkDateIterator:
    """
    For a specific user, iterate the available workdays for that user.
    Taking into account public_holidays and personal_holidays
    """

    def __init__(self, username, public_holidays, personal_holidays, weekdays_off=WEEKDAYS_OFF, start_date=None):
        self.username = username
        self.public_holidays = public_holidays
        self.personal_holidays = personal_holidays
        self.combined_holidays = tuple(list(self.public_holidays) + list(self.personal_holidays))
        self.weekdays_off = weekdays_off
        self.start_date = start_date if start_date else datetime.datetime.utcnow().date()

        # decrement in order to return initial start date and use same next function.
        self.current_date = self.start_date - datetime.timedelta(days=1)

    def __iter__(self):
        return self

    def __next__(self):
        self.current_date += datetime.timedelta(days=1)
        while self.current_date.weekday() in self.weekdays_off or self.current_date in self.combined_holidays:
            self.current_date += datetime.timedelta(days=1)
        return self.current_date


class TaskScheduler:

    def __init__(self, tasks, milestones, public_holidays, assignee_personal_holidays, start_date=None):
        """
        :param tasks: List of Task objects
        :param milestones: List of Milestone objects
        :param assignee_personal_holidays: (dict) of persional holidays (datetime.date()) keyed by task username
        :param start_date: (datetime.date) Start date of scheduling (if not given current UTC value used)
        """
        self.tasks = {t.id: t for t in tasks}
        self.milestones = {m.name: m for m in milestones}
        task_milestone_names = [t.milestone for t in self.tasks.values()]
        for milestone_name in task_milestone_names:
            if milestone_name not in self.milestones:
                raise MissingMilestone(f'Required Milestone definition missing for: {milestone_name}')
        self.public_holidays = public_holidays
        self.assignee_personal_holidays = assignee_personal_holidays
        self._start_date = start_date

    def montecarlo(self, trials=5000):
        """
        Run montecarlo simulation for the number of trials specified
        :param trials: number of trials
        :return: (list) [(SCHEDULED_TASKS, ASSIGNEE_TASKS), ...]
        """
        results = []
        for trial in range(trials):
            result_pair = self.schedule()
            results.append(result_pair)
        return results

    def schedule(self, is_montecarlo=False):
        """
        Schedule tasks given on instantiation
        :param is_montecarlo: (bool) If True, random value selected using triangular distribution
        :return: (dict) scheduled_tasks, assignee_tasks
            scheduled_tasks =
            { TASK_ID: {
                    WORK_DATE,
                    ...
                ], ...
            },
            assignee_tasks =
            { ASSIGNEE_USERNAME: [
                TASK_OBJECT,
                ...
                ],
                ...
            }
        """
        # filter tasks to dependant and non-dependant
        dependant_tasks = {}
        non_dependant_tasks = {}
        unique_assignees = set()
        for task_id, task_details in self.tasks.items():
            if task_details.depends_on:
                dependant_tasks[task_id] = task_details
            else:
                non_dependant_tasks[task_id] = task_details
            for assignee in task_details.assignees:
                unique_assignees.add(assignee)

        # build assignee iterators
        assignees_date_iterators = {}
        for unique_assignee in unique_assignees:
            if unique_assignee not in self.assignee_personal_holidays:
                warnings.warn('personal_holiday date list not given for: {}'.format(unique_assignee))
            personal_holidays = self.assignee_personal_holidays.get(unique_assignee, [])
            # build work date iterator
            assignees_date_iterator = AssigneeWorkDateIterator(unique_assignee,
                                                               self.public_holidays,
                                                               personal_holidays,
                                                               start_date=self._start_date)
            assignees_date_iterators[unique_assignee] = assignees_date_iterator

        # create toposort compatible structure for tasks with dependancies
        dependancies = {}
        for task_id, components in dependant_tasks.items():
            dependant_task_ids = set(components.depends_on)
            dependancies[task_id] = dependant_task_ids

        # get dependancy graph
        dependancy_graph = toposort(dependancies)

        # group tasks by assignee
        # --> Tasks in each group are independant, and can be run in parallel (but user specific)
        all_assignee_tasks = defaultdict(list)
        is_initial = True
        scheduled_tasks = defaultdict(list)
        for task_group in dependancy_graph:
            if is_initial:
                # include non_dependant tasks
                for task_id in non_dependant_tasks.keys():
                    task_group.add(task_id)
                is_initial = False

            # collect task information in current group
            task_details = {task_id: self.tasks[task_id] for task_id in task_group}

            # group tasks by assignnes
            # --> if more than 1 assignee, select 1, and issue warning
            for assignee, assignee_tasks in groupby(task_details.values(), by_assignee):
                # process assignee tasks
                # --> sort by priority, and schedule
                priority_sorted = sorted(assignee_tasks, key=attrgetter('absolute_priority'))
                tasks_to_schedule = len(priority_sorted)
                newly_scheduled = 0
                looped_work_date = None
                while True:
                    for task in priority_sorted:
                        task_id = task.id
                        milestone_name = task.milestone
                        _, milestone_start_date, milestone_end_date = self.milestones[milestone_name]
                        min_estimate, main_estimate, max_estimate = task.estimates
                        if is_montecarlo:
                            # get random number using triangular distribution
                            # -- yes, this would be more efficient if we got a bunch here when running montecarlo,
                            # -- but, it's difficult to do when tasks are inter-dependant.
                            estimate = int(triangular(min_estimate, main_estimate, max_estimate, size=1)[0])
                        else:
                            estimate = main_estimate

                        # Check milestone has started before schduling with assignee
                        if assignees_date_iterators[assignee].current_date >= milestone_start_date:
                            # schedule task for user
                            for day in range(estimate):
                                if looped_work_date:
                                    work_date = looped_work_date
                                    looped_work_date = None
                                else:
                                    work_date = next(assignees_date_iterators[assignee])
                                scheduled_tasks[task_id].append(work_date)
                                newly_scheduled += 1

                            # add to all tasks
                            all_assignee_tasks[assignee].append(task)
                        else:
                            warnings.warn('NOTICE -- Task({}) milestone({}) not yet started!'.format(task_id, milestone_name))
                    # single loop complete,
                    # --> check if fully scheduled, if not increment user dates
                    if newly_scheduled < tasks_to_schedule:
                        # increment
                        looped_work_date = next(assignees_date_iterators[assignee])
                    else:
                        break  # All tasks are scheduled
        return scheduled_tasks, all_assignee_tasks



