#!/usr/bin/env python3
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8090/ready"

def get_status():
    try:
        req = urllib.request.Request(BASE_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except:
            return e.code, None
    except Exception as e:
        return 0, str(e)

def run_docker_cmd(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

print("Starting Resilience Test...")

# Step 1: Ensure system is healthy initially
print("\n[1/4] Verifying initial health...")
status, body = get_status()
if status != 200:
    print(f"FAIL: System is not initially healthy. Status: {status}")
    sys.exit(1)
print("System is healthy.")

# Step 2: Take down Postgres
print("\n[2/4] Simulating Postgres failure (docker stop postgres)...")
run_docker_cmd("docker stop postgres")
time.sleep(3) # Wait for connections to drop and NGINX/Flask to register failure

# Step 3: Verify system degrades gracefully (503 Service Unavailable)
print("\n[3/4] Verifying graceful degradation...")
status, body = get_status()
if status in (502, 503, 504):
    print(f"PASS: System correctly returned 503. Body: {body}")
elif status == 0:
    print(f"FAIL: NGINX crashed or timed out entirely! Status: {status}")
    sys.exit(1)
else:
    print(f"FAIL: Expected 502/503/504, got {status}. Body: {body}")
    sys.exit(1)

# Step 4: Bring Postgres back up and verify recovery
print("\n[4/4] Simulating Postgres recovery (docker start postgres)...")
run_docker_cmd("docker start postgres")
print("Waiting for Postgres to initialize (20 seconds)...")
time.sleep(20)

status, body = get_status()
if status == 200:
    print("PASS: System fully recovered automatically!")
else:
    print(f"FAIL: System failed to recover. Status: {status}. Body: {body}")
    sys.exit(1)

print("\nALL RESILIENCE CHECKS PASSED!")
sys.exit(0)