#!/usr/bin/env python3
# coding: utf-8
# pylint:disable=unused-wildcard-import


"""Build entry point."""

from typing import Any, Dict, List, TextIO
import sys

import doit  # type: ignore

from buildchain import constants
from buildchain.build import *
from buildchain.builder import *
from buildchain.codegen import *
from buildchain.deps import *
from buildchain.docs import *
from buildchain.image import *
from buildchain.iso import *
from buildchain.format import *
from buildchain.lint import *
from buildchain.packaging import *
from buildchain.salt_tree import *
from buildchain.ui import *
from buildchain.vagrant import *


# mypy doesn't know the type of `doit.reporter.JsonReporter`.
class CustomReporter(doit.reporter.JsonReporter):  # type: ignore
    """A custom reporter that display a JSON object for each task."""
    desc = 'console, display the execution of each task, generate a build log'

    def __init__(self, outstream: TextIO, options: Dict[str, Any]):
        super().__init__(outstream, options)
        self.failures : List[Dict[str, Any]] = []
        self.runtime_errors : List[str] = []

    def execute_task(self, task: doit.task.Task) -> None:
        """Called when a task is executed."""
        super().execute_task(task)
        if task.actions:  # Ignore tasks that do not define actions.
            self._write('.  {}\n'.format(task.title()))

    def add_failure(
        self, task: doit.task.Task, exception: doit.exceptions.CatchedException
    ) -> None:
        """Called when execution finishes with a failure"""
        super().add_failure(task, exception)
        result = {'task': task, 'exception':exception}
        self.failures.append(result)
        self._write_failure(result)

    def skip_uptodate(self, task: doit.task.Task) -> None:
        """Called when a task is skipped (up-to-date)."""
        super().skip_uptodate(task)
        self._write('-- {}\n'.format(task.title()))

    def skip_ignore(self, task: doit.task.Task) -> None:
        """Called when a task is skipped (ignored)."""
        super().skip_ignore(task)
        self._write('!! {}\n'.format(task.title()))

    def cleanup_error(
        self, exception: doit.exceptions.CatchedException
    ) -> None:
        """Error during cleanup."""
        self._write(exception.get_msg())

    def runtime_error(self, msg: str) -> None:
        """Error from doit itself (not from a task execution)."""
        # saved so they are displayed after task failures messages
        self.runtime_errors.append(msg)

    def complete_run(self) -> None:
        """Called when finished running all tasks."""
        # If test fails print output from failed task.
        failure_header = '#'*40 + '\n'
        for result in self.failures:
            task = result['task']
            # Makes no sense to print output if task was not executed.
            if not task.executed:
                continue
            self._write(failure_header)
            self._write_failure(result)
            err = ''.join([action.err for action in task.actions if action.err])
            self._write('{} <stderr>:\n{}\n'.format(task.name, err))
            out = ''.join([action.out for action in task.actions if action.out])
            self._write('{} <stdout>:\n{}\n'.format(task.name, out))

        if self.runtime_errors:
            self._write(failure_header)
            self._write('Execution aborted.\n')
            self._write('\n'.join(self.runtime_errors))
            self._write('\n')
        # Generate the build log.
        build_log = constants.ROOT/'build.log'
        with build_log.open('w', encoding='utf-8') as fp:
            self.outstream = fp
            super().complete_run()

    def _write(self, text: str) -> None:
        self.outstream.write(text)

    def _write_failure(self, result: Dict[str, Any]) -> None:
        self._write('{} - taskid:{}\n'.format(
            result['exception'].get_name(), result['task'].name
        ))
        self._write(result['exception'].get_msg())
        self._write('\n')


DOIT_CONFIG = {
    'default_tasks': ['iso'],
    'reporter': CustomReporter,
    'cleandep': True,
    'cleanforget': True,
}

# Because some code (in `doit` or even below) seems to be using a dangerous mix
# of threads and fork, the workers processes are killed by macOS (search for
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY for the details).
#
# Until the guilty code is properly fixed (if ever), let's force the use of
# threads instead of forks on macOS to sidestep the issue.
if sys.platform == 'darwin':
    DOIT_CONFIG['par_type'] = 'thread'
