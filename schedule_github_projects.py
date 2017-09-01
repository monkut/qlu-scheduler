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


def schedule_projects(org, projects, milestone_start_dates, phantom_user_count, montecarlo_trials=0, percentile=90):

    adaptor = GithubOrganizationProjectsAdaptor(org,
                                                projects,
                                                milestone_start_dates,
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
        logger.info(f'Running ({args.montecarlo}) Monte-Carlo Trials!')

    if not args.milestone_start_dates or not os.path.exists(os.path.expanduser(args.milestone_start_dates)):
        raise parser.error(f'Missing path to Milestone StartDates Mapping JSON: {args.milestone_start_dates}')

    milestones_mapping_filepath = os.path.expanduser(args.milestone_start_dates)
    with open(milestones_mapping_filepath, 'r', encoding='utf8') as f:
        milestone_start_dates_json = json.load(f)
    milestone_start_dates = {}
    for milestone_name, start_date_str in milestone_start_dates_json.items():
        start_date = arrow.get(start_date_str).date()
        milestone_start_dates[milestone_name] = start_date

    distributions, completion_estimates = schedule_projects(args.organization,
                                                            args.projects,
                                                            milestone_start_dates,
                                                            args.users,
                                                            args.montecarlo)
    import pprint
    pprint.pprint(distributions)
    pprint.pprint(completion_estimates)



