<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# DevOps Internship Task - Starter v2

This repository contains the completed, secured, and automated deployment environment for the Barq Academy DevOps Internship assessment. The initial broken starter architecture has been fully audited, fixed, and brought up to production readiness.

## Project Setup and Operations

The environment runs two Flask applications behind an NGINX reverse proxy, connected to isolated PostgreSQL and Redis databases.

### 1. Build and Start the Environment
```bash
# Clone the repository
git clone <your-repo-url>
cd barq-academy

# Initialize the configuration files
mkdir -p config
cp .env.example config/app.env
cp .env.example .env # (Provides local variables for docker-compose)

# Start the environment in detached mode
docker compose up -d --build
```

### 2. Run Automated Validation
```bash
# Test network isolation, endpoint liveness, and database/cache functionality
python3 validate.py
```

### 3. Run Resilience / Failure Tests
```bash
# Test the system's ability to handle and recover from database outages
python3 failure_test.py
```

### 4. Backup and Restore
```bash
# Create a full dump of the PostgreSQL database
./backup.sh

# Restore the database from the generated dump file
./restore.sh
```       

### 5. Stop and Cleanup
```bash
# Safely pause the environment without losing database persistence
docker compose stop

# Tear down the environment and wipe all persistent volumes
docker compose down -v
```

---

## Architectural Reflection Questions

### 1. What failed first? What proved the cause? Which failed attempt taught you something?
The very first failure was that NGINX couldn't route traffic to the Flask applications (returning empty responses or Connection Refused). This was proven by running docker exec nginx wget -qO- --timeout=2 http://app-02:8080/ which immediately returned "Connection refused." The root cause was that APP_HOST was bound to 127.0.0.1 inside the containers, blocking external traffic. Later, we also discovered NGINX had *too much* access (it was connected to both the frontend and backend networks); separating it from the backend network taught me the importance of strict micro-segmentation, ensuring the proxy tier cannot bypass the app tier to reach the data layer directly.

### 2. What patterns did the logs reveal? How did you avoid double-counting requests?
Analyzing the historical logs via custom Python/Bash scripts revealed two things: an off-by-one math error in the original P95 latency calculation, and a distinct outage window where app-02 was completely unreachable (throwing 502 Bad Gateway and "Connection refused" errors) between 11:05 and 11:09, while app-01 remained entirely healthy. To avoid double-counting requests, we uniquely identified them by cross-referencing the 
equest_id across the NGINX access logs and the application logs, grouping the data logically rather than blindly counting raw lines.

### 3. How do requests flow? Why these ports, networks and readiness checks?
Requests flow from the external client hitting host port 8080, directly to the NGINX container on the Frontend network. NGINX acts as a reverse proxy, distributing requests round-robin to app-01 and app-02 on internal port 8080. The Flask apps, bridging both networks, query PostgreSQL (5432) and Redis (6379) exclusively on the Backend network. The /ready endpoint explicitly pings both databases because a 200 OK from /health is meaningless if the underlying data tier is offline. 

### 4. Why these timeouts, retries, restart settings and resource limits?
We configured restart: unless-stopped on all services to guarantee resilience against temporary crashes or host reboots. We enforced hard memory limits (512M) per application container to prevent an application memory leak from causing an Out-Of-Memory (OOM) cascade failure that could crash the host machine. We adjusted the startup wait timeouts (sleep 30 in CI, 20s in scripts) specifically because database boot sequences (especially PostgreSQL doing an initial initdb on slower CI runners) require grace periods before they can accept connections.

### 5. When should validation fail? What does green CI prove, or not prove?
Validation should fail immediately if any required HTTP endpoint returns a non-200 status code (or returns a 500 range during a simulated recovery phase), OR if the script successfully connects to port 5432 or 6379 from the host machine (which indicates a critical network isolation failure). A green CI pipeline proves that the code is syntactically correct, the containers build successfully, and the functional integration works locally. It **does not** prove that the system is secure against penetration, nor does it prove that the application will scale or remain stable under production-level traffic loads.

### 6. Which single points of failure remain? How would you fix them in production?
Currently, NGINX, PostgreSQL, and Redis are all single instances. If any of those specific containers die permanently, the entire system goes down or loses functionality. In a true production environment, we would migrate to managed, highly-available databases (such as AWS RDS for PostgreSQL and ElastiCache for Redis) spanning multiple Availability Zones. We would also place a cloud Load Balancer in front of multiple NGINX ingress nodes running in a Kubernetes cluster to eliminate the single proxy bottleneck.

### 7. What would you improve? How did you verify AI-assisted work?
I would improve the security posture by migrating all images from the slim-bookworm or alpine bases to distroless or scratch images, which remove the shell and package managers entirely, drastically reducing the attack surface for Remote Code Execution. I would also implement automated CI/CD container scanning (e.g., Trivy). AI-assisted work was strictly verified by manually running all generated commands locally in WSL, executing and testing the outputs of all scripts, and explicitly auditing the proposed Bash/Python syntax for flaws or hallucinated flags before accepting the commits into the repository.