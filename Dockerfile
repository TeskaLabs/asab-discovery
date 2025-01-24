FROM pcr.teskalabs.com/alpine:3.18 AS building
MAINTAINER TeskaLabs Ltd (support@teskalabs.com)

# Include build environment variables from GitLab CI/CD
ARG CI_COMMIT_BRANCH
ARG CI_COMMIT_TAG
ARG CI_COMMIT_REF_NAME
ARG CI_COMMIT_SHA
ARG CI_COMMIT_TIMESTAMP
ARG CI_JOB_ID
ARG CI_PIPELINE_CREATED_AT
ARG CI_RUNNER_ID
ARG CI_RUNNER_EXECUTABLE_ARCH
ARG GITHUB_HEAD_REF
ARG GITHUB_JOB
ARG GITHUB_SHA
ARG GITHUB_REPOSITORY

ENV LANG C.UTF-8

RUN set -ex \
  && apk update \
  && apk upgrade

RUN apk add --no-cache \
  python3 \
  py3-pip \
  git \
  python3-dev \
  libffi-dev \
  libgit2-dev \
  gcc \
  g++

RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir jinja2 "pygit2<1.12" aiohttp aiozk whoosh pyyaml sentry-sdk
RUN pip3 install "asab[authz] @ git+https://github.com/TeskaLabs/asab.git"

RUN mkdir -p /app/asab-discovery

COPY . /app/asab-discovery
RUN (cd /app/asab-discovery && asab-manifest.py ./MANIFEST.json)

FROM pcr.teskalabs.com/alpine:3.18 AS shiping

RUN apk add --no-cache \
  python3 \
  libgit2

COPY --from=building /usr/lib/python3.11/site-packages /usr/lib/python3.11/site-packages
COPY --from=building /app/asab-discovery/MANIFEST.json /app/MANIFEST.json

COPY ./asabdiscovery      /app/asab-discovery/asabdiscovery
COPY ./asab-discovery.py  /app/asab-discovery/asab-discovery.py
COPY ./CHANGELOG.md     /app/CHANGELOG.md

RUN set -ex \
  && mkdir /conf \
  && touch conf/asab-discovery.conf

VOLUME /var/lib/asab-discovery

WORKDIR /app/asab-discovery
CMD ["python3", "asab-discovery.py", "-c", "/conf/asab-discovery.conf"]
