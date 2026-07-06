# ADR 0001: Generate The Containerfile From An Extension Manifest

## Status

Accepted

## Context

The extension image pins Debian package versions from PGDG and Pigsty, copies only the
files needed by Kubernetes ImageVolume consumers, and intentionally leaves some
packages disabled until their runtime requirements are understood.

A hand-written Containerfile can build the image, but it is a poor substrate for the
planned nightly update workflow. Automation would need to parse ARG names, install
lines, COPY lines, and comments to understand which package versions are current and
which packages are intentionally excluded.

## Decision

Keep `extensions.json` as the source of truth and generate
`images/Containerfile.extensions` from it with a dependency-free Python script. CI must
regenerate the Containerfile and fail when the generated artifact is out of date.

## Consequences

Package update automation can edit structured JSON instead of parsing a Containerfile.
Disabled packages can keep explicit reasons in the manifest. The generated
Containerfile is less inviting for hand edits, so contributors must update the
manifest and rerun the generator.

The nightly update workflow uses the manifest as its edit target: it checks every
package against `apt-cache policy` inside the configured PostgreSQL base image,
updates pins from each package's declared source, regenerates the Containerfile, builds
the image with Podman, and opens a reviewable pull request only when the build
succeeds.
