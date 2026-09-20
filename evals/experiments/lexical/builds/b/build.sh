#!/bin/sh
# Fixed official source archives; writes only a caller-selected temporary context
# and the isolated local medy-dec001-b Docker image. No PostgreSQL data volumes.
set -eu
build_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
context=${1:?usage: build.sh NEW_OR_EXISTING_TEMP_CONTEXT}
mkdir -p "$context"
curl --fail --location --retry 2 --output "$context/zhparser.tar.gz" \
    https://codeload.github.com/amutu/zhparser/tar.gz/dd292fd591edbcb7ebee79d3c3cdc969e9cddced
curl --fail --location --retry 2 --output "$context/scws.tar.gz" \
    https://codeload.github.com/hightman/scws/tar.gz/a04ef5e655213eb6b07fb57761d0eac72c281ad4
(cd "$context" && printf '%s\n' \
    'ae670786b1372337d0527917692e7b40910fff0e3e9a727b3cccc09b73bd5584  zhparser.tar.gz' \
    'c4f83883bf453aa9829a36abea76a11d546016fe639838b72b66bfca9f7f4d0d  scws.tar.gz' | shasum -a 256 --check)
docker build --platform linux/arm64 --progress plain \
    --tag medy-dec001-b:zhparser2.3-scws1.2.3 --file "$build_dir/Dockerfile" "$context"
