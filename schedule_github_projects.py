"""
Script performs monte-carlo simulation to calculate when a github organizational project will complete.
"""

import os
import json
import logging
import arrow
from qlu.adapters.github import GithubOrganizationProjectsAdaptor

logging.basicConfig(format='%(asctime) [%(level)s]: %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


# TODO set this externally
HOLIDAYS = (
    arrow.get('2017-09-18').date(),
    arrow.get('2017-09-22').date(),
    arrow.get('2017-10-09').date(),
    arrow.get('2017-11-03').date(),
    arrow.get('2017-11-23').date(),
    arrow.get('2017-12-23').date(),
    # 2018
    arrow.get('2018-01-01').date(),
    arrow.get('2018-01-08').date(),
    arrow.get('2018-02-11').date(),
    arrow.get('2018-03-21').date(),
)


def schedule_projects(org, projects, milestone_start_dates, phantom_user_count):
    adaptor = GithubOrganizationProjectsAdaptor(org,
                                                projects,
                                                milestone_start_dates,
                                                public_holidays=HOLIDAYS,
                                                phantom_user_count=phantom_user_count)
    scheduler = adaptor.generate_task_scheduler()
    scheduled_tasks, all_assignee_tasks = scheduler.schedule()
    return scheduled_tasks, all_assignee_tasks


def perform_montecarlo(org, projects, milestone_start_dates, phantom_user_count, montecarlo_trials=0, percentile=90):

    adaptor = GithubOrganizationProjectsAdaptor(org,
                                                projects,
                                                milestone_start_dates,
                                                public_holidays=HOLIDAYS,
                                                phantom_user_count=phantom_user_count)
    scheduler = adaptor.generate_task_scheduler()
    assert montecarlo_trials > 0  # Currently this script is for simulating schedules
    distributions, completion_dates = scheduler.montecarlo(montecarlo_trials, percentile)
    return distributions, completion_dates


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--organization',
                        default='abeja-inc',
                        help='Github Organization Name')
    parser.add_argument('-p', '--projects',
                        nargs='+',
                        required=True,
                        help='Projects to consider in scheduling')
    parser.add_argument('-u', '--users',
                        type=int,
                        default=0,
                        help='Number of Phantom users to use in assignment')
    parser.add_argument('-m', '--montecarlo',
                        type=int,
                        default=5000,
                        help='If > 0,  the number of trials specified here will be run')
    parser.add_argument('-s', '--start-dates',
                        dest='milestone_start_dates',
                        help='path to a json file containing a mapping of Milestone names to start dates')
    parser.add_argument('--verbose',
                        action='store_true',
                        default=False,
                        help='If given, DEBUG info will be displayed')
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.montecarlo:
        logger.info('Running ({}) Monte-Carlo Trials!'.format(args.montecarlo))

    if not args.milestone_start_dates or not os.path.exists(os.path.expanduser(args.milestone_start_dates)):
        raise parser.error(f'Missing path to Milestone StartDates Mapping JSON: {args.milestone_start_dates}')

    milestones_mapping_filepath = os.path.expanduser(args.milestone_start_dates)
    with open(milestones_mapping_filepath, 'r', encoding='utf8') as f:
        milestone_start_dates_json = json.load(f)
    milestone_start_dates = {}
    for milestone_name, start_date_str in milestone_start_dates_json.items():
        start_date = arrow.get(start_date_str).date()
        milestone_start_dates[milestone_name] = start_date
    print(milestone_start_dates)

    if args.montecarlo and args.montecarlo > 0:
        distributions, completion_estimates = perform_montecarlo(args.organization,
                                                                args.projects,
                                                                milestone_start_dates,
                                                                args.users,
                                                                args.montecarlo)
        import pprint
        pprint.pprint(distributions)
        pprint.pprint(completion_estimates)
    else:
        estimated_finish_date = None
        scheduled_tasks, assignments = schedule_projects(args.organization,
                                                                args.projects,
                                                                milestone_start_dates,
                                                                args.users)
        # output the per user assignments
        for user, tasks in assignments.items():
            print(user)
            for task in tasks:
                for task_id, dates in scheduled_tasks.items():
                    if task_id == task.id:
                        print('\t{}:'.format(task_id, dates))
                        for d in dates:
                            print('\t\t{}'.format(d))
                        if not estimated_finish_date:
                            estimated_finish_date = d
                        elif d > estimated_finish_date:
                            estimated_finish_date = d
                        break
        print('Estimated Finish Date: {}'.format(estimated_finish_date))




