# Supafull Extensions

Glossary of domain language for the PostgreSQL extension image project. This file is
a dictionary, not a spec; it records what terms mean, not how the project is built.

**Extension Image**:
The published OCI image containing PostgreSQL extension files for a specific
PostgreSQL major version and Debian release. The image is mounted into a PostgreSQL
container; it is not itself a runnable database server.
_Avoid_: database image, Postgres image.

**ImageVolume Payload**:
The read-only filesystem content exposed by the Extension Image when Kubernetes mounts
the image as a volume. The payload contains extension libraries, SQL/control files,
runtime system libraries, and license files.
_Avoid_: sidecar, init container.

**Extension Manifest**:
The checked-in JSON file that records package sources, package names, pinned package
versions, copy behavior, and disabled packages. It is the source of truth for the
generated Containerfile.
_Avoid_: lockfile, package.json.

**Package Source**:
An upstream Debian package repository that supplies PostgreSQL extension packages.
This project currently distinguishes PGDG and Pigsty because update checks and package
version formats differ by source.
_Avoid_: registry, mirror.

**Update PR**:
The automation-owned pull request that refreshes Extension Manifest package pins after
the nightly package check succeeds and the generated Extension Image builds locally in
CI. It is always reviewable; automation never writes package pin changes directly to
`main`.
_Avoid_: auto-upgrade, direct update.

**Release Tag**:
The git tag that names a published Extension Image. It has no leading `v` and includes
the project version, PostgreSQL major version, and Debian codename, for example
`0.0.11-18-trixie`.
_Avoid_: semver tag when omitting the PostgreSQL/Debian compatibility suffix.
