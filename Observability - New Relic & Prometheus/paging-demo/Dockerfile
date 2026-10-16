FROM python:3.15.0-slim
WORKDIR /app
COPY receiver.py .
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8088
CMD ["python", "receiver.py"]
