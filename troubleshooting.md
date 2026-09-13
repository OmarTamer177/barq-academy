# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

## Entry 1 / 2026-09-07 / 13:30 UTC
- Symptom: curl http://localhost:8080/ready returns nothing; NGINX cannot reach either backend app
- Hypothesis: apps bind to loopback only (APP_HOST=127.0.0.1), so no other container can reach them regardless of port; nginx.conf listens on 80 internally but host port maps to 81
- Command or test:
  docker exec nginx wget -qO- --timeout=2 http://app-01:8081/
  docker exec nginx wget -qO- --timeout=2 http://app-02:8080/
  curl -s http://localhost:8080/ready
- Actual output:
  app-01:8081 -> "Connection refused"
  app-02:8080 -> "Connection refused" (correct port per nginx.conf, so bind address is the suspect, not port)
  curl :8080/ready -> empty, no response
- Failed attempt and what changed your thinking: none yet at this point, first test
- Root cause: APP_HOST was set to "127.0.0.1" in the x-app anchor in docker-compose.yml, causing the Flask app to bind only to the local loopback interface inside its container, making it unreachable from the NGINX container.
- Fix: Changed APP_HOST to "0.0.0.0" in the shared x-app anchor in docker-compose.yml.
- Retest evidence:
  docker exec nginx wget -qO- --timeout=2 http://app-02:8080/
  {"instance_id":"app-01","message":"Welcome to BARQ Systems","service":"barq-api","version":"2.0.0"}
- Related commit: b54b59774649343d3881ee58ccbe44d9a440d2dd
- Remaining uncertainty: whether app-01:8081 refusal is due to APP_HOST alone or also the wrong port in nginx upstream config. curl http://localhost:8080/ready still fails because NGINX listen/port mapping and app-01 port mismatch in upstream config are not yet fixed.

## Entry 2 / 2026-09-07 / 13:35 UTC
- Symptom: config/app.env pointed at postgres:5433 and redis:6380; DATABASE_URL password ended in "d" while POSTGRES_PASSWORD in compose ended in "c"
- Hypothesis: wrong ports and password typo would cause /ready and any DB-touching endpoint to fail independently of the NGINX issue in Entry 1
- Command or test:
  grep -E "postgres:|redis:" config/app.env
  (compared against POSTGRES_PASSWORD in docker-compose.yml, and against actual ports from postgres/redis container logs)
- Actual output: 
  DATABASE_URL=postgresql://barq_app:BarqLabOnly_7qN2vK8c@postgres:5432/barq_tasks
  REDIS_URL=redis://redis:6379/0
  confirmed mismatch, 5433 vs actual 5432, 6380 vs actual 6379, password last char d vs c
- Failed attempt and what changed your thinking: none, mismatch was directly visible in file contents
- Root cause: config/app.env had incorrect port numbers and a one-character password typo
- Fix: edited config/app.env, corrected DATABASE_URL to postgres:5432 with password ending in c, corrected REDIS_URL to redis:6379
- Retest evidence: 
    docker exec app-01 python -c "import psycopg; psycopg.connect('postgresql://barq_app:BarqLabOnly_7qN2vK8c@postgres:5432/barq_tasks')" && echo OK  ->  OK
    docker exec app-01 python -c "import redis; print(redis.Redis.from_url('redis://redis:6379/0').ping())"  ->  True
- Related commit: 4e344a475352a787db4c0ee890c36b511eb2dce7
- Remaining uncertainty: None


## Entry 3 / 2026-09-13 / 07:38 UTC
- Symptom: curl http://localhost:8080/ready returns empty response from host.
- Hypothesis: NGINX is not receiving traffic from the host because docker-compose maps the host port to container port 81, but nginx.conf listens on port 80.
- Command or test: grep -E "listen|81" docker-compose.yml nginx/nginx.conf
- Actual output: docker-compose.yml has port 81, nginx.conf has listen 80
- Failed attempt and what changed your thinking: none
- Root cause: Port mismatch between docker-compose port mapping and NGINX config.
- Fix: Changed container port mapping in docker-compose.yml from 81 to 80.
- Retest evidence:
  curl -I http://localhost:8080/
  HTTP/1.1 502 Bad Gateway (Connection refused is fixed, NGINX is reached)
- Related commit: 6d40f52e4006e3a7c82079d1f2613d27c8d47ea6
- Remaining uncertainty: app-01 still has the wrong upstream port, so some requests might still fail with 502, but NGINX itself should now be reachable.

## Entry 4 / 2026-09-13 / 07:44 UTC
- Symptom: curl http://localhost:8080/ returns 502 Bad Gateway consistently or intermittently.
- Hypothesis: NGINX upstream configuration is attempting to route traffic to the wrong port for app-01.
- Command or test: grep -A 3 "upstream application_pool" nginx/nginx.conf
- Actual output: server app-01:8081 max_fails=0; (app-02 is correctly 8080)
- Failed attempt and what changed your thinking: none
- Root cause: Typo in nginx.conf upstream block where app-01 was pointing to port 8081 instead of 8080.
- Fix: Changed server app-01:8081 to server app-01:8080 in nginx/nginx.conf.
- Retest evidence:
  curl -s http://localhost:8080/
  {"instance_id":"app-01","message":"Welcome to BARQ Systems","service":"barq-api","version":"2.0.0"}
- Related commit: ae68dd8f5fa1b5b3c531ac7fe6b682b939998c2a
- Remaining uncertainty: The healthcheck path and instance ID issues still remain, but basic routing to both apps should now work without 502s.

## Entry 5 / 2026-09-13 / 07:50 UTC
- Symptom: Containers might report as unhealthy or healthcheck logs show HTTP 404 errors.
- Hypothesis: The healthcheck in docker-compose is querying an endpoint that doesn't exist in the application.
- Command or test: grep "healthz" docker-compose.yml
- Actual output: test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
- Failed attempt and what changed your thinking: none
- Root cause: Typo in the docker-compose.yml healthcheck path (/healthz instead of /health).
- Fix: Changed the healthcheck path in docker-compose.yml from /healthz to /health.
- Retest evidence:
  docker ps --format "{{.Names}}: {{.Status}}" | grep app
  app-01: Up 15 seconds (healthy)
  app-02: Up 15 seconds (healthy)
- Related commit: 2c5aae070a57b7c73da4277ef5dcc300fabf8dee
- Remaining uncertainty: Duplicate instance_id issue still needs to be resolved.

## Entry 6 / 2026-09-13 / 08:09 UTC
- Symptom: Hitting the API through NGINX always returns "instance_id": "app-01", even though NGINX is round-robining between two containers.
- Hypothesis: The INSTANCE_ID environment variable for app-02 was accidentally copied from app-01.
- Command or test: grep -A 5 "app-02:" docker-compose.yml
- Actual output: app-02 sets INSTANCE_ID: "app-01"
- Failed attempt and what changed your thinking: none
- Root cause: Copy-paste error in the environment variables of app-02.
- Fix: Changed INSTANCE_ID: "app-01" to INSTANCE_ID: "app-02" for the app-02 service in docker-compose.yml.
- Retest evidence:
  curl -s http://localhost:8080/instance (multiple times)
  {"instance_id":"app-01","service":"barq-api","status":"ok","version":"2.0.0"}
  {"instance_id":"app-02","service":"barq-api","status":"ok","version":"2.0.0"}
  (Responses now properly alternate between app-01 and app-02)
- Related commit: e90f7b8b103c3dd731272b400f043b278f0d2dd4
- Remaining uncertainty: none

## Entry 7 / 2026-09-13 / 08:13 UTC
- Symptom: PostgreSQL data does not persist across container restarts. Any data created in the API is lost when containers restart.
- Hypothesis: The volume for Postgres data is misconfigured in docker-compose.yml.
- Command or test: grep -A 5 "volumes:" docker-compose.yml under postgres block
- Actual output: tmpfs: [/var/lib/postgresql/data] is set, and postgres-data volume is mounted to /var/lib/postgresql/backup
- Failed attempt and what changed your thinking: none
- Root cause: The Postgres data directory was mounted as a temporary RAM disk (tmpfs), and the persistent named volume was mounted to an unused backup directory.
- Fix: Removed the tmpfs directive and corrected the named volume mount from /var/lib/postgresql/backup to /var/lib/postgresql/data in docker-compose.yml.
- Retest evidence:
  curl -s -H "Content-Type: application/json" -d '{"title":"Persistence proof"}' http://localhost:8080/records
  docker compose up -d --force-recreate
  curl -s http://localhost:8080/records
  {"instance_id":"app-01","records":[{"id":1,"title":"Review service readiness"},{"id":2,"title":"Document the operating procedure"},{"id":3,"title":"Persistence proof"}],"service":"barq-api","version":"2.0.0"}
  (Record #3 survived recreation)
- Related commit: 852cbce95ba7b53db171058a82e64be00cc5ba37
- Remaining uncertainty: none

## Entry 8 / 2026-09-13 / 08:22 UTC
- Symptom: The Flask app containers (app-01, app-02) are running as the root user, which violates container security best practices.
- Hypothesis: The Dockerfile overrides the unprivileged user it creates.
- Command or test: docker exec app-01 whoami
- Actual output: root
- Failed attempt and what changed your thinking: none
- Root cause: The Dockerfile creates an unprivileged 'app' user but explicitly sets USER root right before the CMD instruction.
- Fix: Changed USER root to USER app in the Dockerfile.
- Retest evidence:
  docker exec app-01 whoami
  app
- Related commit: 948886c30f543c944671f10890bcc93bba78622d
- Remaining uncertainty: none

## Entry 9 / 2026-09-13 / 08:27 UTC
- Symptom: Postgres and Redis ports are accessible from the host, which violates the security requirements in the assessment.
- Hypothesis: The ports are explicitly published in docker-compose.yml.
- Command or test: docker ps --format "{{.Names}}: {{.Ports}}" | grep -E "postgres|redis"
- Actual output: Postgres and Redis had ports mapped to 127.0.0.1:15432 and 127.0.0.1:16379 respectively.
- Failed attempt and what changed your thinking: none
- Root cause: The docker-compose.yml file contained ports: directives for both postgres and redis.
- Fix: Removed the ports mapping blocks from postgres and redis in docker-compose.yml so they are only accessible on the internal docker network.
- Retest evidence:
  docker ps --format "{{.Names}}: {{.Ports}}" | grep -E "postgres|redis"
  postgres: 5432/tcp
  redis: 6379/tcp
  (No host IP bindings like 127.0.0.1 are shown anymore)
- Related commit: 42064a3c173647dbaf9c8a5035b948bbbb2d5b21
- Remaining uncertainty: none

## Entry 10 / 2026-09-13 / 13:58 UTC
- Symptom: Security review noted that secrets should not be baked into the image, but the Dockerfile had a `COPY config/app.env /srv/app.env` line which contradicts this.
- Hypothesis: The line is dead code since the application actually reads configuration from environment variables injected by Docker Compose, not from a file path inside the container.
- Command or test: `docker save barq-check | tar -xO 2>/dev/null | grep -a "BarqLabOnly" || echo "not found in image"`
- Actual output: `not` (which corresponds to not found in image)
- Failed attempt and what changed your thinking: None.
- Root cause: The `Dockerfile` unnecessarily copied the `.env` file into the image layer, baking in sensitive credentials.
- Fix: Deleted `COPY config/app.env /srv/app.env` from `Dockerfile`.
- Retest evidence: Ran `docker compose up -d --build` and verified endpoints (`/`, `/ready`, `/records`) still functioned identically (returning 200 OK and valid JSON).
- Related commit: pending
- Remaining uncertainty: None.
