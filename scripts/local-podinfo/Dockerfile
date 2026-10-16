# Package verified static binaries; no network or build steps run here.
FROM scratch
LABEL org.opencontainers.image.source="https://github.com/stefanprodan/podinfo" \
      org.opencontainers.image.version="6.15.0-security1" \
      org.opencontainers.image.revision="dd507173b7b75b2312a36cabe0de5f09c1ce69c8"
COPY ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY podinfo /podinfo
COPY podcli /usr/local/bin/podcli
COPY ui /ui
COPY LICENSE /LICENSE
COPY --chmod=1777 tmp /tmp
USER 65532:65532
EXPOSE 9898
ENTRYPOINT ["/podinfo"]
