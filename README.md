# qlu-scheduler README

[![CircleCI](https://circleci.com/gh/monkut/qlu-scheduler/tree/master.svg?style=svg)](https://circleci.com/gh/monkut/qlu-scheduler/tree/master)

This project is an attempt to automate much of the manual work of scheduling and tracking 
a software development project.  In addtion, it provides monte-carlo simulation of task schedule delays, enabling you to determine how probable a
given project will finish on time.

It uses the following key components to schedule 1 or more projects:

- Project-ID
    - Identifies a specific Project

- QluMilestone (`qlu.core.QluMilestone`)
    - Defines a specific Milestone with start/end dates

- QluTask (`qlu.core.QluTask`)
    - Defines a given task with associated Project, (optional) Milestone, (optional) Assignee, and QluTaskEstimates

- QluTaskEstimate (`qlu.core.QluTaskEstimate`)
    - Defines the min, expected, and max estimate days needed for completion of a task

- Assignee
    - Defines a specific assignee to which a task is assigned and performed by.


Sample Instantiation & Usage:

```python
WORKDAYS = {'assignee-name': ['Mon', 'Tue', 'Wed']}
PERSONAL_HOLIDAYS = {
    'assignee-name': [
        datetime.date(2019, 6, 1),
    ]
}
scheduler = QluTaskScheduler(milestones=TEST_MILESTONES,
                             public_holidays=PUBLIC_HOLIDAYS,
                             assignee_workdays=WORKDAYS,
                             assignee_personal_holidays=PERSONAL_HOLIDAYS,
                             start_date=START_DATE)
result_schedule = scheduler.schedule(TASKS)
```

## Why not just auto-assign tasks?

Yes, a scheduler has the ability to identify available resources, and automatically assign tasks.
However, in a software development project with many participants, there is a large variation of skill sets and knowledge.
If you can manage to capture this skill set variance, it would be more practical to auto-assign, but still difficult to take in all factors.

So, assignment is left to the humans, and the goal of *qlu-scheduler* is to make it easier to understand the current state of the project,
and determine how probable it is that the project will finish 

## Qlu Key Components

The following components are used for `qlu scheduling`:

- QluTasks

- QluMilestones (*optional*)

- holiday_calendar (*optional*)

- Assignee Personal Holidays (*optional*) Per user holday dates

- Start Date

### QluTasks

QluTasks define a specific amount of work.
A task may be linked to a *milestone*.  If linked to a milestone a task will *NOT* be assigned *until* the milestone *start-date* is reached.


### QluMilestones

A milestone may be optionally defined in order to control when a task or group of tasks can start.
In addition, a milestone defines a target *end-date*, allowing you to identify when a task or tasks are predicted to be past the expected due date.


### holiday_calendar

(*optional*)

When Public holidays are defined, these dates will *NOT* be included as work days when calculating the schedule.

 - `from pandas.tseries.holiday import AbstractHolidayCalendar` object, used to define the public holidays to NOT include as workdays in resulting schedule.

### Assignee Personal Holidays

(*optional*)

When defiend for a specific user, these dates will *NOT* be included as work days for the user when calculating the schedule.


### Start Date

This is the date by which a project starts.


## Target Views

This project targets the ability to generate the following views:

- Absolute Priority
    - Display a list of ALL tasks in the total priority 
    - Multi-Repository (Github Organization Projects support multiple repositories in a single project)
    
- User View
    - Display task load of ALL users
    
- Gantt Chart per project (all charts on single screen?)
    - Main Estimate
    - Monte-Carlo 90%
    
## About Monte-Carlo Simulation

The implemented monte-carlo simulation uses a triangle distribution based on min, expected, max estiamtes of a given task to run multiple trials, 
and determine that a given percentage of those trials finish at a certain time.

The main difference will be seen when a given task has dependencies    