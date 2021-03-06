# coding: utf-8

"""Targets to write files from Python objects."""

import enum
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from buildchain import types
from buildchain import utils

from . import base


def render_json(obj: Any, filepath: Path) -> None:
    """Serialize an object as JSON to a given file path."""
    with filepath.open('w', encoding='utf-8') as file_obj:
        json.dump(obj, file_obj, sort_keys=True, indent=2)


def render_envfile(variables: Mapping[str, str], filepath: Path) -> None:
    """Serialize a dict as an env file to the given file path."""
    with filepath.open('w', encoding='utf-8') as fp:
        data = '\n'.join(
            '{}={}'.format(key, value) for key, value in variables.items()
        )
        fp.write(data)
        fp.write('\n')


class Renderer(enum.Enum):
    """Supported rendering methods for `SerializedData` targets."""
    JSON = 'JSON'
    ENV  = 'ENV'


class SerializedData(base.AtomicTarget):
    """Serialize an object into a file with a specific renderer."""

    RENDERERS = {
        Renderer.JSON: render_json,
        Renderer.ENV:  render_envfile,
    }

    def __init__(
        self,
        data: Any,
        destination: Path,
        renderer: Renderer = Renderer.JSON,
        **kwargs: Any
    ):
        """Configure a file rendering task.

        Arguments:
            data:        object to render into a file
            destination: path to the rendered file

        Keyword Arguments:
            They are passed to `Target` init method
        """
        kwargs['targets'] = [destination]
        super().__init__(**kwargs)

        self._data = data
        self._dest = destination

        if not isinstance(renderer, Renderer):
            raise ValueError(
                'Invalid `renderer`: {!r}. Must be one of: {}'.format(
                    renderer, ', '.join(map(repr, Renderer))
                )
            )

        self._renderer = renderer

    @property
    def task(self) -> types.TaskDict:
        task = self.basic_task
        task.update({
            'title': utils.title_with_target1(
                'RENDER {}'.format(self._renderer.value)
            ),
            'doc': 'Render file "{}" with "{}"'.format(
                self._dest, self._renderer
            ),
            'actions': [self._run],
        })
        return task

    @property
    def _render(self) -> Callable[[Any, Path], None]:
        return self.RENDERERS[self._renderer]

    def _run(self) -> None:
        """Render the file."""
        self._render(self._data, self._dest)
