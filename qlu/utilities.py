"""Utilities to assist in project scheduling."""
import warnings
from functools import partial
from typing import List, Iterable, Callable, Generator, Dict, Tuple, Hashable
from numpy.random import uniform
from .core import QluTask

DEFAULT_PHANTOM_USERNAME_PREFIX = 'phantom-'
DEFAULT_DISTRIBUTION_CALLABLE = uniform


class AssigneeChooser:
    """A helper class to unify the distribution callable interface"""

    def __init__(self, assignees: Iterable[Hashable], distribution: Callable=DEFAULT_DISTRIBUTION_CALLABLE, dargs: Tuple=None, dkwargs: Dict=None):
        """
        :param assignees: assignee ids or names to
        :param distribution:
        :param dargs:
        :param dkwargs:
        """
        if not dargs:
            dargs = tuple()
        if not dkwargs:
            dkwargs = dict()

        self.assignees = list(assignees)
        if distribution is uniform and not dargs:
            if not dkwargs:
                dkwargs = {
                    'low': 0,
                    'high': len(assignees)  # inclusive
                }
        self._choice_func = partial(distribution, *dargs, **dkwargs)

    def choice(self):
        assignee_index = int(self._choice_func())
        return self.assignees[assignee_index]


class PhantomUserAssignmentManager:
    """Utilities for creating a PhantomUser for QluTask assignment.
    """

    def __init__(self, phantom_user_count):
        """
        :param phantom_user_count: (int) Number of 'phantom' users to assign unassigned tasks to
            .. note::

                Intended to help with determining how many Resources are needed for the project.

        """
        self.user_count = phantom_user_count
        self.usernames = self.get_phantom_usernames(phantom_user_count)

    def get_phantom_usernames(self, user_count: int, usesrname_prefix=DEFAULT_PHANTOM_USERNAME_PREFIX) -> List[str]:
        """
        Create and return the usernames to be used for phantom users.

        :param user_count:
        :param usesrname_prefix: Prefix to use for created names.
        :return: created usernames
        """
        assert user_count

        # add phantom users if defined
        usernames = []  # used for assignment
        for i in range(user_count):
            name = f'{usesrname_prefix}{i}'
            usernames.append(name)
        return usernames

    def assign(self, tasks: Iterable[QluTask],
               distribution_func: Callable=DEFAULT_DISTRIBUTION_CALLABLE,
               dargs: tuple=None, dkwargs: Dict=None) -> Generator[QluTask, None, None]:
        """
        Assign configured phantom users to Unassigned QluTasks.

        :param tasks:Tasks containing unnassigned QluTasks
        :param distribution_func: A random sampling distribution from numpy.random.

            .. note::

                See https://docs.scipy.org/doc/numpy-1.14.0/reference/routines.random.html for available distribution functions
        :param dargs: arguments to pass to the distribution callable
        :param dkwargs: keyword arguments to pass to the distribution callable
        :return:
            .. code:: python

                [QluTask(), QluTask(), ]

        """
        assert tasks

        # prepare distribution for usage
        assignee_chooser = AssigneeChooser(self.usernames, distribution_func, dargs, dkwargs)
        count = 0
        for count, qlu_task in enumerate(tasks, 1):
            if not qlu_task.assignee:
                assignee = assignee_chooser.choice()
                warnings.warn('Assigning Phantom User: {}'.format(assignee))
                qlu_task.assignee = assignee
                yield qlu_task
            else:
                yield qlu_task
        assert count
