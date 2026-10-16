FROM cgr.dev/chainguard/nginx@sha256:bbed24ea6459404aeaf23edca30844092adee4d6059808cda5ebf9456a43d874
WORKDIR /app
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 8080
USER 65532:65532

ENTRYPOINT ["/usr/sbin/nginx"]
CMD ["-c", "/etc/nginx/nginx.conf", "-e", "/dev/stderr", "-g", "daemon off;"]
