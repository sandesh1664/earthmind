# ADR 0005: native ARM64 containers and explicit reproducibility limits

Status: accepted for M01.

Require a native ARM64 Docker engine. Every Compose service declares
`linux/arm64`; custom build stages assert the target and Debian architecture.
Pin base image indexes by digest and retain actual registry platform evidence.
Never enable QEMU or silently fall back to AMD64.

Application dependencies are locked, Python build tooling is pinned, and
PostGIS/SUMO top-level Debian package versions are explicit. A clean build must
fail if those exact packages disappear rather than silently select new engine
versions. Transitive Debian/PGDG packages still come from live repositories;
these builds are not claimed to be byte-identical or permanently available.
An immutable apt snapshot or retained release images would be needed for that
stronger guarantee.
