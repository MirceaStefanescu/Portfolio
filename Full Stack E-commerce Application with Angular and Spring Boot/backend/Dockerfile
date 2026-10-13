FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B -DskipTests dependency:go-offline
COPY src src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
ARG JAR_FILE=target/ecommerce-0.0.1-SNAPSHOT.jar
COPY --from=build /app/${JAR_FILE} app.jar
COPY docker-healthcheck.sh /app/docker-healthcheck.sh
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 CMD ["bash", "/app/docker-healthcheck.sh"]
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
