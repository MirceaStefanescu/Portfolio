FROM alpine:3.24

RUN adduser -D appuser
WORKDIR /app
COPY index.html /app/index.html
EXPOSE 8080
USER appuser

CMD ["sh", "-c", "busybox httpd -f -p 8080 -h /app"]
