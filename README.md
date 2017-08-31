# qlu-scheduler README

This project is an attempt to automate much of the manual work of scheduling and tracking 
a software development project, and provide monte-carlo simulation of task schedule delays, enabling you to determine how probable a
given project will finish on time.

It uses the following key components to schedule a project:

- Project

- Milestone

- Task

- TaskEstimate

- Assignee


## Why not just auto-assign tasks?

Yes, a scheduler has the ability to identify available resources, and automatically assign tasks.
However, in a software development project with many participants, there is a large variation of skill sets and knowledge.
If you can manage to capture this skill set variance, it would be more practical to auto-assign, but still difficult to take in all factors.

So, assignment is left to the humans, and the goal of *qlu-scheduler* is to make it easier to understand the current state of the project,
and determine how probable it is that the project will finish 



## Views

- Absolute Priority
    - Display a list of ALL tasks in the total priority 
    - Multi-Repository
    - Multi-Project
    
- User View
    - Display task load of ALL users
    
- Gantt Chart per project (all charts on single screen?)
    - Main Estimate
    - Monte-Carlo 90%