"""Generate the Eve YAML description of build plan for MetalK8s."""
import sys

from buildplan import core
from buildplan import yamlprint


def build_project():
    project = core.Project()
    project.add(pre_merge())
    return project


# Stages {{{
def pre_merge():
    return core.Stage(
        name="pre-merge",
        worker=core.LocalWorker(),
        branches=[
            "user/*",
            "feature/*",
            "improvement/*",
            "bugfix/*",
            "w/*",
            "q/*",
            "hotfix/*",
            "dependabot/*",
            "documentation/*",
            "release/*",
        ],
        steps=[
            core.TriggerStages(
                "Trigger build, docs, and lint stages",
                stages=[build(), docs(), lint()],
            ),
            set_version_property(),
            core.TriggerStages(
                "Trigger single-node and multiple-nodes steps with built ISO",
                stages=[single_node(), multiple_nodes()],
            ),
        ],
    )


def build():
    return core.Stage(
        name="build",
        worker=core.KubePodWorker(
            path="eve/workers/pod-builder/pod.yaml",
            images=[
                core.KubePodWorker.Image(
                    name="docker-builder", context="eve/workers/pod-builder"
                )
            ],
        ),
        steps=[],
    )


def docs():
    return core.Stage(
        name="docs",
        worker=core.KubePodWorker(
            path="eve/workers/pod-docs-builder/pod.yaml",
            images=[
                core.KubePodWorker.Image(
                    name="doc-builder",
                    context=".",
                    dockerfile="docs/Dockerfile",
                )
            ],
        ),
        steps=[],
    )


def lint():
    return core.Stage(
        name="lint",
        worker=core.KubePodWorker(
            path="eve/workers/pod-linter/pod.yaml",
            images=[
                core.KubePodWorker.Image(
                    name="docker-linter", context="eve/workers/pod-linter"
                )
            ],
        ),
        steps=[],
    )


def single_node():
    return core.Stage(
        name="single-node",
        worker=core.OpenStackWorker(
            path="eve/workers/openstack-single-node",
            flavor=core.OpenStackWorker.Flavor.LARGE,
            image=core.OpenStackWorker.Image.CENTOS7,
        ),
        steps=[],
    )


def multiple_nodes():
    return core.Stage(
        name="multiple-nodes",
        worker=core.OpenStackWorker(
            path="eve/workers/openstack-multiple-nodes",
            flavor=core.OpenStackWorker.Flavor.MEDIUM,
            image=core.OpenStackWorker.Image.CENTOS7,
        ),
        steps=[],
    )


# }}}
# Steps {{{
def set_version_property():
    return core.SetPropertyFromCommand(
        "Set version as property from built artifacts",
        property_name="metalk8s_version",
        command=(
            "bash -c '"
            '. <(curl -s "%(prop:artifacts_private_url)s")'
            " && echo $VERSION'"
        ),
    )


# }}}

if __name__ == "__main__":
    build_plan = build_project().dump()
    yamlprint.dump(build_plan, stream=sys.stdout)
