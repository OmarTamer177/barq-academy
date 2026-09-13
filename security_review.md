# Security and production-readiness review

Record at least 8 concrete risks or improvements relevant to your final solution.
This is a review requirement, not the number of hidden faults.

For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.

## Completed Work

### 1. Container User
- Risk and evidence: The Flask application containers were running as the root user. The Dockerfile created an unprivileged 'app' user but explicitly declared USER root before the final CMD. 
- Impact: If the application were compromised (e.g. via remote code execution), the attacker would have root privileges inside the container, increasing the risk of container escape and broader system compromise.
- Implemented fix / commit: Changed USER root to USER app in the Dockerfile. (Commit: 948886c30f543c944671f10890bcc93bba78622d)
- Production follow-up: Implement automated container image scanning and a policy engine (like OPA/Gatekeeper) to block deployments of containers running as root.
- How to verify: Run docker exec app-01 whoami and verify it returns app.

### 2. Ports
- Risk and evidence: Postgres and Redis had their default ports explicitly published to the host machine in docker-compose.yml (127.0.0.1:15432:5432 and 127.0.0.1:16379:6379).
- Impact: Databases were exposed to the host system and potentially broader networks if misconfigured, bypassing NGINX entirely. Attackers could interact with the database directly.
- Implemented fix / commit: Removed the ports mappings from both postgres and redis in docker-compose.yml. (Commit: 42064a3c173647dbaf9c8a5035b948bbbb2d5b21)
- Production follow-up: Ensure cloud security groups or Kubernetes network policies explicitly deny external ingress to database ports.
- How to verify: Run docker ps --format "{{.Names}}: {{.Ports}}" and confirm postgres/redis only have internal ports open.

### 3. Networks
- Risk and evidence: NGINX was attached to both the Frontend and Backend networks in docker-compose.yml, granting it direct network access to the databases.
- Impact: A vulnerability in the public-facing NGINX proxy could allow an attacker to pivot directly to the databases, bypassing the application layer's security controls and logic.
- Implemented fix / commit: Removed the Backend network from NGINX so it can only communicate with the Flask apps on the Frontend network. 
- Production follow-up: Enforce strict micro-segmentation using network policies so the proxy tier can never route to the data tier.
- How to verify: Run docker inspect nginx and verify only the Frontend network is attached.

### 4. Persistence/Backup
- Risk and evidence: Both database services lacked persistent storage. Postgres mounted its primary data directory (/var/lib/postgresql/data) to a tmpfs (RAM disk), meaning data was wiped on every restart. Redis was explicitly disabling persistence via --save "" and --appendonly "no".
- Impact: Complete data loss for PostgreSQL and Redis upon any container restart or crash.
- Implemented fix / commit: For Postgres: removed the tmpfs mount and correctly mapped the persistent Docker volume (Commit: 852cbce95ba7b53db171058a82e64be00cc5ba37). For Redis: changed the command to --appendonly "yes" and mapped a 
edis-data volume.
- Production follow-up: In production, configure automated backups for Postgres. Use managed databases (RDS/ElastiCache) with automated snapshots.
- How to verify: Create a record via the API and hit the /counter endpoint. Recreate the containers, query the API, and verify the record and counter survived.

### 5. Secrets
- Risk and evidence: The `config/app.env` file containing real PostgreSQL and Redis passwords was tracked in the Git repository.
- Impact: Anyone with read access to the repository could extract production credentials, leading to full data compromise.
- Implemented fix / commit: Removed the file from Git tracking (`git rm --cached`), added it to `.gitignore`, and provided a sanitized `.env.example`. and scrubbed the hardcoded POSTGRES_PASSWORD directly from \docker-compose.yml\, forcing it to read from the secure environment instead.
- Production follow-up: All leaked passwords must be rotated immediately. In production, migrate to a dedicated secret manager (e.g., AWS Secrets Manager, HashiCorp Vault) rather than env files.
- How to verify: Run `git ls-files | grep app.env` to ensure it returns empty, and inspect `.gitignore`.

Note: The synthetic lab password is visible in early commit history despite being removed from current tracking; git rm --cached doesn't purge history. Since the task requires preserving baseline commit history, it wasn't scrubbed. In a real environment this credential would be rotated immediately, but here it's documented as an accepted, low-stakes exposure since it's synthetic lab data rather than a real secret.

### 6. Availability and Resource Limits
- Risk and evidence: `docker-compose.yml` had no resource limits defined, and the app containers were explicitly set to `restart: "no"`.
- Impact: A single runaway container (e.g., memory leak) could consume all host RAM, crashing the entire server. App crashes would cause permanent downtime until manually restarted.
- Implemented fix / commit: Added `restart: unless-stopped` and `deploy.resources.limits` (0.5 CPU, 512M memory) to all services.
- Production follow-up: Deploy across multiple physical nodes/availability zones using Kubernetes with Horizontal Pod Autoscaling (HPA).
- How to verify: Run `docker stats` and verify the memory limits column shows 512MiB.

## Planned/Future Improvements

### 7. Logging and Monitoring
- Risk and evidence: Application and error logs are currently only stored locally on the Docker host via standard output.
- Impact: If the host machine dies, all forensic log data is permanently lost, severely hindering incident response.
- Implemented fix / commit: None (Planned) - Configure Docker's logging driver (`syslog` or `fluentd`) in `docker-compose.yml` to forward logs to a centralized cluster (ELK stack or Datadog).
- Production follow-up: Set up alerting for 5xx errors and latency spikes above the P95 baseline.
- How to verify: Check the `logging:` section of future compose files and verify logs appear in the centralized dashboard.

### 8. Image Selection
- Risk and evidence: We are using `python:3.12-slim-bookworm` and `nginx:1.28-alpine`. While SHA-pinned, they still contain a full package manager and shell.
- Impact: If an attacker achieves Remote Code Execution (RCE), they have the tools (like `apk` or `apt`) to download additional malware.
- Implemented fix / commit: None (Planned) - Migrate all application images to "Distroless" base images or `scratch`, which contain only the application binary and its immediate dependencies.
- Production follow-up: Enforce strict automated vulnerability scanning (e.g., Trivy, Clair) in the CI pipeline before pushing to the registry.
- How to verify: Run `docker exec app-01 sh` on a distroless container; it should fail because no shell exists.
