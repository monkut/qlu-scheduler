# qlu-scheduler README

This project is an attempt to automate much of the manual work of scheduling and tracking 
a software development project.  In addtion, it provides monte-carlo simulation of task schedule delays, enabling you to determine how probable a
given project will finish on time.

It uses the following key components to schedule a project:

- Project

- Milestone

- Task

- TaskEstimate

- Assignee


Sample Instantiation & Usage:

```python
scheduler = TaskScheduler(tasks=TEST_TASKS_NONE_ASSIGNED,
                          milestones=TEST_MILESTONES,
                          public_holidays=PUBLIC_HOLIDAYS,
                          assignee_personal_holidays=PERSONAL_HOLIDAYS,
                          phantom_user_count=14,
                          start_date=START_DATE)
scheduled_tasks_four, assignee_tasks = scheduler.schedule()
```

## Why not just auto-assign tasks?

Yes, a scheduler has the ability to identify available resources, and automatically assign tasks.
However, in a software development project with many participants, there is a large variation of skill sets and knowledge.
If you can manage to capture this skill set variance, it would be more practical to auto-assign, but still difficult to take in all factors.

So, assignment is left to the humans, and the goal of *qlu-scheduler* is to make it easier to understand the current state of the project,
and determine how probable it is that the project will finish 

## Qlu Key Components

The following components are used for `qlu scheduling`:

- Tasks

- Milestones (*optional*)

- Pubic Holidays (*optional*)

- Assignee Personal Holidays (*optional*)

- Phantom User Count (*optional*)

- Start Date

### Tasks

Tasks define a specific amount of work.
A task may be linked to a *milestone*.  If linked to a milestone a task will *NOT* be assigned *until* the milestone *start-date* is reached.


### Milestones

(*optional*)

A milestone may be optionally defined in order to control when a task or group of tasks can start.
In addition, a milestone defines a target *end-date*, allowing you to identify when a task or tasks are predicted to be past the expected due date.


### Public Holidays

(*optional*)

When Public holidays are defined, these dates will *NOT* be included as work days when calculating the schedule.

### Assignee Personal Holidays

(*optional*)

When defiend for a specific user, these dates will *NOT* be included as work days for the user when calculating the schedule.

### Phantom User Count

(*optional*)

*Phatom Users* are intended to be used for project planning.
When defined they will be used to randomlly assign tasks to in the calculation of a schedule.

The intention is to provide a method by which to estimate when a project will end given a number of workers.

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