#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error
import socket

BASE_URL = "http://127.0.0.1:8080"
passed = True

def check(name, url, method="GET", data=None, expected_status=200):
    global passed
    print(f"Checking {name} ({method} {url})... ", end="")
    try:
        req_data = json.dumps(data).encode('utf-8') if data else None
        headers = {'Content-Type': 'application/json'} if data else {}
        req = urllib.request.Request(BASE_URL + url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=2) as resp:
            status = resp.status
            body = json.loads(resp.read().decode('utf-8'))
            
            if status != expected_status:
                print(f"FAIL: Expected status {expected_status}, got {status}")
                passed = False
                return None
            
            print("PASS")
            return body
    except urllib.error.HTTPError as e:
        print(f"FAIL: HTTPError {e.code}")
        passed = False
        return None
    except Exception as e:
        print(f"FAIL: Exception {e}")
        passed = False
        return None

def check_port_closed(port, name):
    global passed
    print(f"Checking {name} Isolation (Port {port})... ", end="")
    try:
        # If we can connect to the host port, it is exposed!
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            print(f"FAIL: Port {port} is accessible from the host!")
            passed = False
    except (ConnectionRefusedError, socket.timeout):
        print("PASS (Connection Refused/Timeout)")

# 0. Check network isolation
check_port_closed(5432, "PostgreSQL")
check_port_closed(6379, "Redis")

# 1. Check /health
check("Health Endpoint", "/health")

# 2. Check /ready
ready_resp = check("Ready Endpoint", "/ready")
if ready_resp and ready_resp.get("status") != "ready":
    print("FAIL: Ready status is not 'ready'")
    passed = False

# 3. Create a record
record_title = "Automated Test Record"
create_resp = check("Create Record", "/records", method="POST", data={"title": record_title}, expected_status=201)

# 4. Check /records (ensure record was created)
records_resp = check("List Records", "/records")
if records_resp and create_resp:
    created_id = create_resp["record"]["id"]
    found = any(r["id"] == created_id and r["title"] == record_title for r in records_resp["records"])
    if not found:
        print(f"FAIL: Record {created_id} not found in GET /records")
        passed = False

# 5. Check Redis caching via /counter
counter1 = check("Counter Check 1", "/counter")
counter2 = check("Counter Check 2", "/counter")

if counter1 and counter2:
    val1 = counter1.get("counter")
    val2 = counter2.get("counter")
    if val2 != val1 + 1:
        print(f"FAIL: Counter did not increment properly. {val1} -> {val2}")
        passed = False

if passed:
    print("\nALL CHECKS PASSED!")
    sys.exit(0)
else:
    print("\nSOME CHECKS FAILED.")
    sys.exit(1)