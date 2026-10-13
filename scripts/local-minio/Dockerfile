# Community container images were withdrawn upstream. Build the pinned official sources.
FROM golang:1.27.2-bookworm AS server-build
RUN git clone https://github.com/minio/minio.git /src && cd /src && git checkout 9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
WORKDIR /src
RUN CGO_ENABLED=0 go build -p 4 -trimpath -o /out/minio .

FROM golang:1.27.2-bookworm AS client-build
RUN git clone https://github.com/minio/mc.git /src && cd /src && git checkout 7394ce0dd2a80935aded936b09fa12cbb3cb8096
WORKDIR /src
RUN CGO_ENABLED=0 go build -p 4 -trimpath -o /out/mc .

FROM debian:trixie-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*

FROM base AS server
COPY --from=server-build /out/minio /usr/bin/minio
COPY --from=server-build /src/dockerscripts/docker-entrypoint.sh /usr/bin/docker-entrypoint.sh
COPY --from=server-build /src/LICENSE /usr/share/doc/minio/LICENSE
ENTRYPOINT ["/usr/bin/docker-entrypoint.sh"]
CMD ["minio"]

FROM base AS client
COPY --from=client-build /out/mc /usr/bin/mc
COPY --from=client-build /src/LICENSE /usr/share/doc/mc/LICENSE
ENTRYPOINT ["/usr/bin/mc"]
