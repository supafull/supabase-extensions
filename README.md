# Supabase PostgreSQL Extensions Image

This repository builds a PostgreSQL extension filesystem payload for Kubernetes
ImageVolume mounts. The image is intended for CloudNativePG PostgreSQL 18 clusters
running on Debian trixie, but the final artifact is a generic scratch image with
extension files under predictable paths.

Published image tags follow this shape:

```text
ghcr.io/supafull/supabase-extensions:0.0.11-18-trixie
```

Tags do not use a leading `v`. The suffix records the PostgreSQL major version and
Debian codename the image was built for.

## What Is In The Image

The image contains files copied from PostgreSQL extension Debian packages:

- `/lib` - PostgreSQL extension shared libraries and bitcode
- `/share/extension` - PostgreSQL extension control and SQL files
- `/system` - extra runtime system libraries not already present in the base image
- `/licenses` - Debian package copyright files when available

The image is built from `ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie` in a
builder stage and published as a `scratch` filesystem payload.

## CloudNativePG Usage

Use the image from a CloudNativePG cluster through the `extensions` image volume
configuration:

```yaml
spec:
  imageName: ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
  postgresql:
    shared_preload_libraries:
      - pg_cron
      - pg_net
      - pgsodium
  managed:
    extensions:
      - name: supabase
        image:
          reference: ghcr.io/supafull/supabase-extensions:0.0.11-18-trixie
```

Exact CloudNativePG field placement can vary with the operator version and chart you
use. The important contract is that this image is mounted as the extension payload
for a PostgreSQL 18 trixie cluster image.

## Generic ImageVolume Usage

The artifact is not CloudNativePG-specific. Any Kubernetes setup that can mount an
OCI image as a read-only volume can consume the filesystem and mount the relevant
directories into the PostgreSQL container.

The PostgreSQL server image must be ABI-compatible with the extension packages. For
this image, that means PostgreSQL 18 on Debian trixie.

## Manifest And Generation

`extensions.json` is the source of truth for package names, pinned versions, source
repositories, copy behavior, and disabled packages. The Containerfile is generated:

```sh
python3 scripts/generate-containerfile.py
```

CI checks that `images/Containerfile.extensions` matches the manifest before building
the image. Do not edit the generated Containerfile by hand.

## Releasing

Push a tag with no leading `v`:

```sh
git tag 0.0.11-18-trixie
git push upstream 0.0.11-18-trixie
```

GitHub Actions publishes:

```text
ghcr.io/supafull/supabase-extensions:0.0.11-18-trixie
```

Pull requests and pushes to `main` build the image without publishing it.

## Package Updates

Package versions are pinned in `extensions.json`. To check for newer package pins
locally, run:

```sh
python3 scripts/update-package-pins.py
```

The updater uses `podman` to run `apt-cache policy` inside the same PostgreSQL base
image used by the builder stage, then selects the newest version from each package's
declared source in `extensions.json`.

The nightly GitHub Actions workflow:

1. Check PGDG and Pigsty for newer package versions.
2. Update `extensions.json`.
3. Regenerate `images/Containerfile.extensions`.
4. Build the image with Podman.
5. Open or update the `automation/update-extension-pins` pull request if the build succeeds.

If no package pins change, the nightly workflow exits successfully without opening or
updating a pull request. Enabled packages that disappear from their declared package
source fail the workflow; disabled packages that disappear are reported but do not
block enabled-package updates.

## Disabled Packages

Disabled packages remain in `extensions.json` with `enabled: false` and a reason. They
are not installed or copied into the final image until their runtime requirements are
understood. The nightly updater still refreshes their pinned versions when their
declared package source publishes a newer compatible version.
