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

### 4. Persistence/Backup (Partial)
- Risk and evidence: The postgres service mounted its primary data directory (/var/lib/postgresql/data) to a tmpfs (RAM disk), meaning data was wiped on every restart.
- Impact: Complete data loss for PostgreSQL upon any container restart or crash.
- Implemented fix / commit: Removed the tmpfs mount and correctly mapped the persistent Docker volume to the data directory. (Commit: 852cbce95ba7b53db171058a82e64be00cc5ba37)
- Production follow-up: We still need to configure backups for Postgres, and we still need to fix Redis persistence (currently disabled). In production, use managed databases (RDS/ElastiCache) with automated snapshots.
- How to verify: Create a record via the API, recreate the containers, and query the API to ensure the record survived.
