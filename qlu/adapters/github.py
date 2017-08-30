import json
import os
import warnings
import arrow
from ghorgs.managers import GithubOrganizationManager
from ..core import TaskScheduler, Task, TaskEstimates, Milestone


NO_ESTIMATES = TaskEstimates(0, 0, 0)

class GithubIssue:

    def __init__(self, issue_json):
        self.data = json.loads(issue_json)

    @property
    def milestone(self):
        name = self.data['milestone']['url']
        start_date = None
        end_date = arrow.get(self.data['milestone']['']).date()
        return Milestone(name, start_date, end_date)

    @property
    def task(self):
        # 'absolute_priority',
        # 'id',
        # 'depends_on',
        # 'estimates',
        # 'assignees',
        # 'project',
        # 'milestone',
        pass

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


class GithubOrganizationProjectsAdaptor:
    """
    Class provides an adaptor for github organization projects to
    qlu Task/TaskEstiamtes/Milestones/

    NOTE: Only 1 project supported
    """

    def __init__(self, organization, project, public_holidays=None, personal_holidays=None, start_date=None):
        token = os.environ.get('GITHUB_OAUTH_TOKEN', None),
        self.project_manager = GithubOrganizationManager(token, organization)
        self.project = project  # organizational project name
        self.public_holidays = public_holidays
        self.personal_holidays = personal_holidays
        self.start_date = start_date
        self.milestones = set()

    def _collect_tasks(self):
        """
        Collect Issues from projects and convert to qlu Task objects
        :return:
        """
        tasks = []
        issue_state_index = 3
        issue_url_index = 5
        for project in self.project_manager.projects():
            if project.name in self.project:
                for issue_object in project.issues():
                    issue = issue_object.simple
                    issue_url = issue[issue_url_index]
                    if issue[issue_state_index] != 'open':
                        warnings.warn(f'Issue not in open STATE, SKIPPING: {issue_url}')
                        continue
                    # convert issue to qlu task!
                    # TaskEstimates = namedtuple('TaskEstimates', ('minimum', 'suggested', 'maximum'))
                    # Task = namedtuple('Task', (
                    #     'absolute_priority',
                    #     'id',
                    #     'depends_on',
                    #     'estimates',
                    #     'assignees',
                    #     'project',
                    #     'milestone',
                    # ))

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
                        warnings.warn(f'Expected "estimate:N" label NOT attached: {issue_url}')
                        estimates = NO_ESTIMATES
                    else:
                        estimate_values = []
                        for offset, estimate_type in enumerate(QLU_GITHUB_ESTIMATE_LABEL_PREFIXES, -1):
                            fallback_value = main_estimate
                            if offset < 0:
                                fallback_value = main_estimate/1.5
                            elif offset > 0:
                                fallback_value = main_estimate * 2
                            value = parsed_estimates.get(estimate_type, fallback_value)
                            estimate_values.append(value)
                        estimates = TaskEstimates(*estimate_values)

                    # priority is based on column position and issue(card) position in the column
                    issue_column_index = 4
                    column = issue[issue_column_index]
                    # expect project matches expected format, should have ALL expected columns
                    assert column in QLU_GITHUB_COLUMNS  # TODO: Add check for project columns prior to processing

                    # Only process issues in ACTIVE columns
                    column_priority_index = 15
                    absolute_priority = None
                    for p, column_name in  enumerate(QLU_GITHUB_ACTIVE_COLUMN_PRIORITY, 1):
                        base_priority = p * 1000
                        if column in QLU_GITHUB_ACTIVE_COLUMN_PRIORITY:
                            column_priority = issue[column_priority_index]
                            absolute_priority = p + column_priority

                    issue_number_index = 1
                    identifier = issue[issue_number_index]  # more unique than ID
                    task = Task(absolute_priority,
                                identifier,
                                issue_object.depends_on,
                                estimates,
                                [a.login for a in issue_object.assignees],
                                issue_object._project.name,
                                issue_object.milestone.title,
                                )
                    self.milestones.add(issue_object.milestone.title)
                    tasks.append(task)
        return tasks

    def _collect_milestones(self):
        """
        Collect Milestones from projects and convert to qlu Milestone objects
        :return:
        """
        return self.milestones

    def generate_task_scheduler(self):
        tasks = self._collect_tasks()
        milestones = list(self._collect_milestones())
        scheduler = TaskScheduler(tasks=tasks,
                                  milestones=milestones,
                                  public_holidays=[],
                                  assignee_personal_holidays=[],
                                  start_date=self.start_date)
        return scheduler
