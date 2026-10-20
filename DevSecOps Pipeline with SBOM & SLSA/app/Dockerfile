FROM cgr.dev/chainguard/nginx@sha256:2031a31bfd755368f6778cf6b295afe83ceb4018d176868698a9db9f811f9bc9
WORKDIR /app
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 8080
USER 65532:65532

ENTRYPOINT ["/usr/sbin/nginx"]
CMD ["-c", "/etc/nginx/nginx.conf", "-e", "/dev/stderr", "-g", "daemon off;"]
