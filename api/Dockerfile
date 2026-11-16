# Dockerfile -- the REST service and the pages of the mini market (mm-api.jar) in a container. The jar is
# built before on the computer (mvnw package: run_docker.ps1 does it), so the image only adds a Java
# runtime. The database: through the wallet of the Forms (mounted read-only at /wallet) and a tnsnames.ora
# whose MM_DB is the database of the computer (host.docker.internal), mounted at /tns: docker-compose.yml.
FROM eclipse-temurin:17-jre-jammy
RUN useradd --system --no-create-home --shell /usr/sbin/nologin mm
WORKDIR /app
COPY target/mm-api.jar /app/mm-api.jar
ENV MM_API_BIND=0.0.0.0 \
    MM_API_PORT=8090 \
    MM_DB_URL=jdbc:oracle:thin:/@MM_DB \
    MM_TNS_ADMIN=/tns \
    MM_WALLET=/wallet
EXPOSE 8090
USER mm
# healthy: its /api/health answers (the service and its database)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/8090 && printf "GET /api/health HTTP/1.0\r\n\r\n" >&3 && grep -q "\"db\":\"ok\"" <&3'
ENTRYPOINT ["java", "-Xmx512m", "-jar", "/app/mm-api.jar"]
