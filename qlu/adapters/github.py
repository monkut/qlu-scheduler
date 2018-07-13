"""
This is an adaptor for github organization projects.
It expects that your projects contain the columns defined in QLU_GITHUB_COLUMNS.
Where, it considers ACTIVE prioritized tasks to in columns defined in QLU_GITHUB_ACTIVE_COLUMN_PRIORITY.
"""
import os
import warnings
import arrow
from ghorgs.managers import GithubOrganizationManager
from ..core import QluTaskScheduler, QluTask, QluTaskEstimates, QluMilestone, MissingQluMilestone


class MissingRequiredEnvironmentVariable(Exception):
    pass


NO_ESTIMATES = QluTaskEstimates(0, 0, 0)

# these are labels defined by qlu so estimates can be processed
QLU_GITHUB_ESTIMATE_LABEL_PREFIXES = (
    'estimate-min',
    'estimate',
    'estimate-max',
)
QLU_GITHUB_LABEL_SEPARATOR = ':'

QLU_GITHUB_COLUMNS = (
    'backlog',
    'planning',
    'in-progress',
    'production-ready',
    'in-production',
)

# lower is better
QLU_GITHUB_ACTIVE_COLUMN_PRIORITY = (
    'in-progress',  # higher priority
    'planning',
)
QLU_GITHUB_DEPENDSON_LABEL_PREFIX = 'depends-on'


class InvalidGithubOrganizationProject(Exception):
    pass


class GithubOrganizationProjectsAdaptor:
    """Class provides an adaptor for github organization projects to
    qlu Task/TaskEstimates/Milestones

    NOTE: Only 1 project supported
    """

    def __init__(self, organization,
                 projects,
                 milestone_start_dates=None,
                 holiday_calendar=None,
                 personal_holidays=None,
                 phantom_user_count=0,
                 start_date=None,
                 milestone_start_date_now=False):
        token = os.environ.get('GITHUB_OAUTH_TOKEN', None)
        if not token:
            raise MissingRequiredEnvironmentVariable('Required GITHUB_OAUTH_TOKEN EnVar not set!')
        self.project_manager = GithubOrganizationManager(token, organization)
        self.projects = projects  # organizational projects name
        self.milestone_start_dates = milestone_start_dates if milestone_start_dates is not None else {}
        self.holiday_calendar = holiday_calendar
        self.personal_holidays = personal_holidays
        self.phantom_user_count = phantom_user_count
        self.start_date = start_date
        self.fallback_milestone_start_date = None
        if milestone_start_date_now:
            self.fallback_milestone_start_date = arrow.utcnow().date()
        self.milestones = {}
        self._tasks = None

    def _collect_tasks(self):
        """Collect Issues from projects and convert to qlu Task objects
        :return:
        """
        tasks = []
        issue_state_index = 3
        issue_url_index = 5
        projects_processed = []
        available_projects = []
        for project in self.project_manager.projects():
            available_projects.append(project.name)
            if project.name in self.projects:
                for issue_object in project.issues():
                    if not issue_object.milestone:
                        msg = (f'Milestone not assigned to Issue({issue_object.id}) [{issue_object.url}], '
                               f'all Issues must be assigned to a Milestone!')
                        raise MissingQluMilestone(msg)
                    issue = issue_object.simple
                    issue_url = issue[issue_url_index]
                    if issue[issue_state_index] != 'open':
                        warnings.warn('Issue not in open STATE, SKIPPING: {}'.format(issue_url))
                        continue

                    # convert issue to qlu task!
                    # get labels from task to define the estimates
                    # --> See QLU_GITHUB_ESTIMATE_LABEL_PREFIXES for expected labels
                    issue_label_index = 7
                    labels = issue[issue_label_index]
                    parsed_estimates = {}
                    for label in labels:
                        if label.startswith(QLU_GITHUB_ESTIMATE_LABEL_PREFIXES):
                            estimate_type, value = label.split(QLU_GITHUB_LABEL_SEPARATOR)
                            parsed_estimates[estimate_type] = int(value)

                    main_estimate = parsed_estimates.get('estimate', None)
                    if not main_estimate:
                        warnings.warn('Expected "estimate:N" label NOT attached: {}'.format(issue_url))
                        estimates = NO_ESTIMATES
                    else:
                        estimate_values = []
                        for offset, estimate_type in enumerate(QLU_GITHUB_ESTIMATE_LABEL_PREFIXES, -1):
                            fallback_value = main_estimate
                            if offset < 0:
                                fallback_value = main_estimate/1.2  # min
                            elif offset > 0:
                                fallback_value = main_estimate * 1.6  # max
                            value = parsed_estimates.get(estimate_type, fallback_value)
                            estimate_values.append(value)
                        estimates = QluTaskEstimates(*estimate_values)

                    # priority is based on column position and issue(card) position in the column
                    issue_column_index = 4
                    column = issue[issue_column_index]

                    # expect project matches expected format, should have ALL expected columns
                    assert column in QLU_GITHUB_COLUMNS

                    # Only process issues in ACTIVE columns
                    column_priority_index = 15
                    absolute_priority = None
                    for p, column_name in enumerate(QLU_GITHUB_ACTIVE_COLUMN_PRIORITY, 1):
                        base_priority = p * 1000
                        if column in QLU_GITHUB_ACTIVE_COLUMN_PRIORITY:
                            column_priority = issue[column_priority_index]
                            absolute_priority = base_priority + column_priority
                    if absolute_priority is None:
                        warnings.warn('Issue not in Project ACTIVE COLUMN({}), SKIPPING: {}'.format(QLU_GITHUB_ACTIVE_COLUMN_PRIORITY,
                                                                                                    issue_object.html_url))
                        continue

                    task = QluTask(
                        issue_object.id,
                        absolute_priority,
                        issue_object.depends_on,
                        estimates,
                        [a.login for a in issue_object.assignees],
                        issue_object._project.name,
                        issue_object.milestone.title,
                    )

                    # Note Github milestone's don't have a start_date component!
                    milestone_start_date = self.milestone_start_dates.get(issue_object.milestone.title,
                                                                          self.fallback_milestone_start_date)
                    github_milestone = QluMilestone(issue_object.milestone.title,
                                                    milestone_start_date,
                                                    arrow.get(issue_object.milestone.due_on).date())
                    self.milestones[issue_object.milestone.title] = github_milestone
                    tasks.append(task)
            projects_processed.append(project.name)
        for p in self.projects:
            if p not in projects_processed:
                raise InvalidGithubOrganizationProject('Project "{}" not in: {}'.format(p, available_projects))
        self._tasks = tasks
        print('_tasks:', self._tasks)
        return tasks

    def _collect_milestones(self):
        """
        Collect Milestones from projects and convert to qlu Milestone objects
        :return:
        """
        # TODO: properly support milestone handling
        return self.milestones.values()

    def generate_task_scheduler(self):
        tasks = self._collect_tasks()
        milestones = list(self._collect_milestones())
        scheduler = QluTaskScheduler(milestones=milestones,
                                     holiday_calendar=self.holiday_calendar,
                                     assignee_personal_holidays=self.personal_holidays,
                                     phantom_user_count=self.phantom_user_count,
                                     start_date=self.start_date)
        return scheduler.schedule(tasks)
