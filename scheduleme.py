"""
Milestone defines when the task CAN start
assignee schedule can define when the
"""
import datetime
from itertools import groupby
from operator import itemgetter
from collections import defaultdict, namedtuple
from toposort import toposort
from numpy.random import triangular


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
            print('WARNING -- More than 1 assignee, selecting the first, sorted alphanumerically')
            assignee = sorted(assignees)[0]
        else:
            assignee = assignees[0]
    else:
        # pick and auto assign
        print('ERROR -- no assignee for task')
        assert assignees
    return assignee


SATURDAY = 5
SUNDAY = 6
WEEKDAYS_OFF = (SATURDAY, SUNDAY)
PUBLIC_HOLIDAYS = (
    datetime.date(2017, 9, 23),
    datetime.date(2017, 9, 15),
    datetime.date(2017, 9, 4),
)
PERSONAL_HOLIDAYS = (
    datetime.date(2017, 10, 15),
    datetime.date(2017, 10, 9),
)


class AssigneeWorkDateIterator:
    """
    For a specific user, iterate the available workdays for that user.
    Taking into account the
    """

    def __init__(self, username, public_holidays=PUBLIC_HOLIDAYS, personal_holidays=PERSONAL_HOLIDAYS,
                 weekdays_off=WEEKDAYS_OFF, start_date=None):
        self.public_holidays = public_holidays
        self.personal_holidays = personal_holidays
        self.combined_holidays = self.public_holidays + self.personal_holidays
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


# Required Components for task scheduling
# (ABSOLUTE_PRIORITY, TASK_ID, [DEPENDS_ON, ..], (ESTIMATE_MIN, ESTIMATE_PROBABLE, ESTIMATE_MAX), [ASSIGNEE-A, ASSIGNEE-B], PROJECT, MILESTONE)

MILESTONES = {
    # NAME: (STARTDATETIME, ENDDATETIME)
    'milestone-a': (
        datetime.datetime(2017, 9, 15).date(),
        datetime.datetime(2017, 10, 20).date(),
    ),
    'milestone-b': (
        datetime.datetime(2017, 10, 3).date(),
        datetime.datetime(2017, 10, 19).date(),
    )
}

tasks = {
    # prioritized tasks
    1: (1, 1, None, (3, 9, 15), ['user-a'], 'project-a', 'milestone-a'),
    2: (3, 2, {1}, (3, 9, 15), ['user-a'], 'project-a', 'milestone-b'),
    3: (2, 3, None, (3, 9, 15), ['user-b'], 'project-a', 'milestone-a'),
}

# fitlter tasks to dependant and non-dependant
dependant_tasks_index = 2
assignees_index = 4
dependant_tasks = {}
non_dependant_tasks = {}
unique_assignees = set()
for task_id, task_details in tasks.items():
    if task_details[dependant_tasks_index]:
        dependant_tasks[task_id] = task_details
    else:
        non_dependant_tasks[task_id] = task_details
    for assignee in task_details[assignees_index]:
        unique_assignees.add(assignee)

# create toposort compatable structure for tasks with dependancies
dependancies = {}
for task_id, components in dependant_tasks.items():
    dependant_task_ids = components[dependant_tasks_index]
    dependancies[task_id] = dependant_task_ids

# 1. get dependancy graph
dependancy_graph = toposort(dependancies)

# 2. group tasks by assignee
# --> Tasks in each group are independant, and can be run in parrallel (but user specific)
all_assignee_tasks = defaultdict(list)
is_initial = True
is_montecarlo = True
task_priority_index = 0
task_id_index = 1
task_estimates_index = 3
task_milestone_index = 6
scheduled_tasks = defaultdict(list)
assignees_date_iterators = {u: AssigneeWorkDateIterator(u) for u in unique_assignees}
for task_group in dependancy_graph:
    if is_initial:
        # include non_dependant tasks
        for task_id in non_dependant_tasks.keys():
            task_group.add(task_id)
        is_initial = False

    # collect task information in current group
    task_details = {task_id: tasks[task_id] for task_id in task_group}

    # group tasks by assignnes
    # --> if more than 1 assignee, select 1, and issue warning
    for assignee, assignee_tasks in groupby(task_details.values(), by_assignee):
        # process assignee tasks
        # --> sort by priority, and schedule
        currently_scheduled = len(scheduled_tasks)
        priority_sorted = sorted(assignee_tasks, key=itemgetter(task_priority_index))
        tasks_to_schedule = len(priority_sorted)
        newly_scheduled = 0
        looped_work_date = None
        while True:
            for task in priority_sorted:
                task_id = task[task_id_index]
                milestone_name = task[task_milestone_index]
                milestone_start_date, milestone_end_date = MILESTONES[milestone_name]
                min_estimate, main_estimate, max_estimate = task[task_estimates_index]
                if is_montecarlo:
                    # get random number using triangular distribution
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
                    print('NOTICE -- Task({}) milestone({}) not yet started!'.format(task_id, milestone_name))
            # single loop complete,
            # --> check if fully scheduled, if not increment user dates
            if newly_scheduled < tasks_to_schedule:
                # increment
                looped_work_date = next(assignees_date_iterators[assignee])
            else:
                break

                # process scheduling~
                # --> use user data to define the number of days/hours
                # --> take into the holidays and milestones

import pprint

pprint.pprint(all_assignee_tasks)
pprint.pprint(scheduled_tasks)


