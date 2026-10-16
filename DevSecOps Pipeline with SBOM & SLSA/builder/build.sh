#!/bin/sh
set -eu
# The isolated worker only sees these public inputs. No host socket, credentials,
# package repository, source checkout, signing key or writable root filesystem.
test -f /src/index.html
test ! -L /src/index.html
test "$(find /src -mindepth 1 -maxdepth 1 | wc -l)" -eq 1
test ! -e /var/run/docker.sock
test ! -e /keys/cosign.key
cp /src/index.html /out/index.html
sha256sum /out/index.html
