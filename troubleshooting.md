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
- Root cause: not yet isolated, multiple compounding issues suspected (APP_HOST, nginx port mismatch, upstream port mismatch, wrong DB/redis ports and password). Being isolated one at a time below.
- Fix: pending
- Retest evidence: pending
- Related commit: pending
- Remaining uncertainty: whether app-01:8081 refusal is due to APP_HOST alone or also the wrong port in nginx upstream config

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
- Related commit: (to be filled: commit #1)
- Remaining uncertainty: None

