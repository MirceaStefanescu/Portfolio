FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package

FROM flink:1.17.2-scala_2.12-java11
WORKDIR /opt/flink
COPY --from=build /app/target/predictive-analytics-job.jar /opt/flink/usrlib/predictive-analytics-job.jar
CMD ["/bin/sh", "-c", "sleep 15 && /opt/flink/bin/flink run -d -m flink-jobmanager:8081 -c com.portfolio.pipeline.flink.PredictionJob /opt/flink/usrlib/predictive-analytics-job.jar && sleep infinity"]
