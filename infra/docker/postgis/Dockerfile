# The upstream postgis/postgis:17-3.6 image has no ARM64 manifest.
# Extend the verified official PostgreSQL ARM64 image with PGDG ARM64 packages.
FROM postgres:17-bookworm@sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27

ARG TARGETARCH
ARG POSTGIS_PACKAGE_VERSION=3.6.4+dfsg-2.pgdg12+1
RUN test "$TARGETARCH" = arm64 \
    && test "$(dpkg --print-architecture)" = arm64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        "postgresql-17-postgis-3=$POSTGIS_PACKAGE_VERSION" \
        "postgresql-17-postgis-3-scripts=$POSTGIS_PACKAGE_VERSION" \
    && dpkg-query -W postgresql-17-postgis-3 \
    && rm -rf /var/lib/apt/lists/*

COPY infra/docker/postgis/10-postgis.sql /docker-entrypoint-initdb.d/10-postgis.sql
