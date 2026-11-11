# syntax=docker/dockerfile:1.7
ARG OPENCODE_VERSION=1.17.3

FROM ghcr.io/anomalyco/opencode:${OPENCODE_VERSION} AS opencode

FROM python:3.12-alpine AS build
RUN apk add --no-cache build-base libstdc++ libgcc git
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-alpine
RUN apk add --no-cache ca-certificates git libstdc++ libgcc ripgrep tini \
    && addgroup -g 10001 -S crb \
    && adduser -u 10001 -S -D -h /home/crb -G crb crb \
    && mkdir -p /workspace/repo /out /cache/code-review-graph /run/secrets /home/crb \
    && chown -R 10001:10001 /workspace /out /cache /home/crb
COPY --from=opencode /usr/local/bin/opencode /usr/local/bin/opencode
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
ENV PYTHONUNBUFFERED=1 \
    HOME=/home/crb \
    XDG_CONFIG_HOME=/home/crb/.config \
    XDG_DATA_HOME=/home/crb/.local/share \
    XDG_CACHE_HOME=/home/crb/.cache \
    GRAPH_CACHE_DIR=/cache/code-review-graph
USER 10001:10001
WORKDIR /workspace/repo
ENTRYPOINT ["/sbin/tini", "--", "crb"]
CMD ["review"]
