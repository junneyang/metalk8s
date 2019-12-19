FROM centos:7

ARG BUILDBOT_VERSION=0.9.12
ARG TERRAFORM_VERSION=0.12.3

WORKDIR /home/eve/workspace

RUN chown eve:eve /home/eve/workspace

RUN yum install -y epel-release \
    && yum install -y \
    curl \
    git \
    make \
    python-pip \
    unzip \
    && pip install buildbot-worker==${BUILDBOT_VERSION}

ARG TF_URL=https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}
ARG TF_FILE=terraform_${TERRAFORM_VERSION}_linux_amd64.zip

RUN curl \
    --retry 5 \
    -O "${TF_URL}/${TF_URL}" \
    && sudo unzip "${TF_FILE}" -d /usr/local/sbin/ \
    && rm -f "${TF_FILE}" \
    && if ! terraform --version 2&> /dev/null; then \
          echo "aborting - terraform not installed and required" >&2; \
          exit 1; \
       fi

USER eve
