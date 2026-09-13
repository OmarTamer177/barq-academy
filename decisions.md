# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.

## 1. Restart Policy
- Choice: Configured all containers with `restart: unless-stopped`.
- Why: It respects manual administrative actions. If an operator stops a container for maintenance, the daemon will not aggressively try to boot it back up. It only restarts containers that crash unexpectedly or when the host machine reboots.
- Alternative: Using `restart: always` or `restart: on-failure`.
- Trade-off: `always` would prevent manual maintenance stops, while `on-failure` wouldn't restart containers on docker daemon reboot. `unless-stopped` gives the best of both.
- Evidence / commit: Added `restart: unless-stopped` to all services in `docker-compose.yml`.
- Production improvement: Kubernetes handles restarts natively; this is a solid interim Docker Compose solution.

## 2. Resource Limits
- Choice: Capped all containers at half a CPU core (0.5) and 512MB of memory.
- Why: This creates a safe sandbox preventing "noisy neighbor" problems where one memory leak crashes the host. The limits are generous enough for a lightweight Python Flask API and Alpine-based Redis/NGINX instances, while remaining strictly contained.
- Alternative: Leaving containers unbounded or setting extremely tight limits (e.g. 128MB).
- Trade-off: Tight limits risk OOM kills under load, while unbounded containers risk crashing the entire host server. 512MB is a safe middle ground.
- Evidence / commit: Added `deploy.resources.limits` to all services in `docker-compose.yml`.
- Production improvement: Set requests AND limits in Kubernetes to ensure QoS classes.

## 3. Network Segmentation
- Choice: Removed NGINX from the `backend` network, isolating it exclusively to the `frontend` network.
- Why: NGINX acts as our edge proxy and only needs to communicate with the Flask apps. Giving it direct access to PostgreSQL and Redis violates the principle of least privilege. By segmenting the networks, an NGINX exploit cannot easily pivot to the data tier.
- Alternative: Keep all containers on a single flat `default` network.
- Trade-off: A flat network is easier to configure but exposes all backend databases to a compromised frontend proxy.
- Evidence / commit: Updated `networks` configuration for the `nginx` service in `docker-compose.yml`.
- Production improvement: Implement strict Kubernetes Network Policies or a service mesh with mTLS.

## 4. Healthcheck Method
- Choice: The Flask apps use a `python urllib` command to hit their own HTTP `/health` endpoint rather than a generic TCP port check.
- Why: A TCP check only proves the socket is open, not that the application is functional. The HTTP check proves the Flask routing engine is alive and responding. We used python's built-in `urllib` to avoid installing `curl` in the image, keeping the attack surface smaller.
- Alternative: Using a simple TCP ping or installing `curl`.
- Trade-off: Installing `curl` increases the image footprint and attack surface, while a TCP ping provides a false sense of security if the app logic is deadlocked. `urllib` is a clean, native compromise.
- Evidence / commit: Added HTTP healthcheck array using `urllib` to `app` services in `docker-compose.yml`.
- Production improvement: Separate liveness, readiness, and startup probes in Kubernetes.

## 5. PostgreSQL Volume
- Choice: Removed the `tmpfs` mount for `/var/lib/postgresql/data` and replaced it with a named Docker volume `postgres-data`.
- Why: `tmpfs` stores data purely in host RAM. This guarantees total data destruction upon container stop. Named volumes ensure data persists safely on the host disk across container lifecycles.
- Alternative: Using a bind mount (`./data:/var/lib/postgresql/data`).
- Trade-off: Bind mounts are dependent on host filesystem permissions and paths, which can break across OS boundaries (e.g. WSL/Windows vs Linux). Named volumes are managed by Docker and are universally cross-platform safe.
- Evidence / commit: Mapped `postgres-data` volume in `docker-compose.yml`.
- Production improvement: Use a managed database service (like AWS RDS) with automated snapshot backups, removing the need for local volumes entirely.