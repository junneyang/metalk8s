# coding: utf-8


"""Common types definitions and aliases."""


from typing import Any, Callable, Dict, List, Tuple, Union

import docker  # type: ignore
import doit    # type: ignore


# A doit action.
Action = Union[
    # A Python function with no arguments.
    Callable[[], Any],
    # A Python function with variable number of arguments and keyword arguments.
    Tuple[Callable[..., Any], List[Any], Dict[str, Any]],
    # A shell command (as a list of string).
    List[str],
]

# An uptodate item (see https://pydoit.org/dependencies.html#uptodate).
UpToDateCheck = Union[
    # True for always up-to-date or False for never up-to-date
    bool,
    # Placeholder for dynamically computed value.
    None,
    # A Python callable.
    Callable[..., Any],
    # A Shell command
    str,
]

# A doit task.
Task = doit.task.Task

# A doit task (as dict)
TaskDict = Dict[str, Any]

# A doit task error
TaskError = doit.exceptions.TaskError

# A docker mount
Mount = docker.types.Mount
