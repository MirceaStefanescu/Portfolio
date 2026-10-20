FROM cgr.dev/chainguard/nginx@sha256:8a42fb9468e353a6c2501d2657866333b7a2a075912f4a7e4fa73298aafd46d6
WORKDIR /app
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 8080
USER 65532:65532

ENTRYPOINT ["/usr/sbin/nginx"]
CMD ["-c", "/etc/nginx/nginx.conf", "-e", "/dev/stderr", "-g", "daemon off;"]
