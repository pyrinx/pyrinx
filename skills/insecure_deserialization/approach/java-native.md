# Java Native Deserialization

## Purpose

Test endpoints that pass attacker-controlled data to `ObjectInputStream.readObject()` or equivalent Java native serialization sinks, enabling remote code execution through classpath gadget chains.

## Applicability

- Java application (any framework: Spring, Struts, JSF, custom)
- Input contains binary blob — base64 prefix `rO0` or raw bytes `ac ed 00 05`
- Endpoints using Java RMI, JMX, custom binary protocols, or HTTP with binary `Content-Type`
- Session cookies, `data` parameters, or hidden fields with opaque base64 content

## Preconditions

- User-controlled data reaches `ObjectInputStream.readObject()` without prior HMAC verification, OR HMAC is weak/bypassable
- At least one gadget chain library present on the server classpath (Commons Collections, Spring Core, Commons BeanUtils, ROME, Groovy, JDK-only chains)
- Network egress available for OAST callback, OR timing oracle usable for blind confirmation

## Relevant Architecture

```
HTTP request (cookie / param / body)
    → base64 decode (or raw bytes over binary protocol)
    → ObjectInputStream.readObject()
    → class lookup (ClassLoader)
    → object graph reconstruction (readObject hooks, constructors, setters)
    → gadget chain → exec / file write / JNDI lookup
```

RMI/JMX paths skip the HTTP layer; the sink is the same `ObjectInputStream` boundary.

## Technical Knowledge

**Magic bytes**
- Hex: `ac ed 00 05`
- Base64: starts with `rO0`

**Gadget chain families (ysoserial)**

| Chain | Library required | Notes |
|-------|-----------------|-------|
| `CommonsCollections1-7` | Commons Collections ≤ 3.2.1 or 4.0 | Most common; variant depends on CC version |
| `CommonsCollections6` | CC 3.x/4.x; works on Java 8+ without `sun.reflect` | Use when CC1 fails on newer JDK |
| `CommonsBeanutils1` | Commons BeanUtils 1.x | Usable with only CB + Commons Logging |
| `Spring1`/`Spring2` | Spring Core | Useful in Spring-heavy apps without CC |
| `ROME` | ROME RSS library | Seen in Jenkins and similar tools |
| `Groovy1` | Groovy ≤ 2.3 | Less common; check Grails apps |
| `URLDNS` | JDK only (no extra library) | **Safe oracle** — DNS callback only, no exec |
| `JRMPClient` | JDK only | Opens outbound JRMP connection |

**JEP 290 / serialization filters (Java 9+)**
- Global or per-`ObjectInputStream` filter on class names, graph depth, array size
- Presence does not mean the filter blocks gadget chains — verify the filter pattern
- `URLDNS` uses `URL` + `HashMap` — often allowed even with filters; test it first

## Indicators

**In HTTP traffic**
- Cookie value decodes from base64 to bytes starting `ac ed 00 05`
- `Content-Type: application/x-java-serialized-object`
- Parameter named `session`, `state`, `data`, `object`, `payload` with long base64 value
- Error responses containing `java.io.InvalidClassException`, `ClassNotFoundException`, `serialVersionUID`

**In source code**
```java
ObjectInputStream ois = new ObjectInputStream(inputStream);
Object obj = ois.readObject();
// or via framework: Spring's HttpInvokerServiceExporter, RemoteInvocationUtils
```

## Interpretation

1. **Magic byte present** → sink highly likely reachable; proceed to chain selection
2. **`InvalidClassException` with class name in error** → confirms deserialization sink and leaks classpath class names
3. **`ClassNotFoundException`** → class not on classpath; try a different chain
4. **No error change on truncated payload** → data may be encrypted/wrapped before deserialization; pivot to `signed-state`
5. **DNS callback fires (`URLDNS`) but exec chain fails** → sink reached; classpath lacks the exec gadget; enumerate classpath further or try `JRMPClient` + secondary service

## Security-Relevant Conditions

- **No serialization filter**: Any chain matching classpath is exploitable
- **Filter allows `java.util.*`, `java.net.*`**: `URLDNS` likely passes; exec chains may not — test both
- **Custom `readObject` on a value class**: May still call `defaultReadObject` first, then apply unsafe logic — read the implementation
- **RMI/JMX exposed on internal port**: Often no auth; full deserialization sink on the registry connection
- **Spring `HttpInvokerServiceExporter`**: Deserializes `RemoteInvocation` — functionally equivalent to raw `ObjectInputStream`

## Experiment Considerations

- Always start with `URLDNS` (DNS callback only) — confirms sink without exec noise
- Use interactsh or Burp Collaborator as the OAST listener
- Match chain to fingerprinted library versions — wrong chain = silent failure
- For RMI: use `ysoserial JRMPClient` against registry, then separate payload on the listener
- Prefer `CommonsCollections6` on Java 8u191+ when CC1 fails (module system restricts `sun.reflect`)
- Do NOT fire exec chains in production without explicit authorization — use `sleep` or DNS only

## Evidence Expectations

1. `URLDNS` payload sent → DNS query observed at interactsh listener → sink confirmed
2. Exec chain payload sent → `id` / `whoami` output returned (OOB if blind) → RCE confirmed
3. Document: exact parameter/cookie name, encoding (raw bytes vs. base64), chain name, library version fingerprint, JDK version if determinable

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| No DNS callback from `URLDNS` | Egress filtered, wrong parameter, or data verified before deserialize |
| `ClassNotFoundException` | Chain class not on classpath; try another chain |
| `InvalidClassException: serialVersionUID mismatch` | Library version mismatch; adjust or try alternate chain |
| `java.io.StreamCorruptedException` | Data is encrypted or re-encoded before deserialization |
| Exec chain fires but no output | Blind RCE; use OOB (curl/DNS) as command |

## False Positives

- Base64 blob starts with `rO0` but is actually a signed JWT or encrypted token — check surrounding context for HMAC/signature fields
- `ObjectInputStream` present in source but receives data from a trusted internal service only — verify data flow from user input
- JEP 290 filter rejects all unknown classes — confirm filter pattern actually covers the gadget chain classes

## Limitations

- Classpath enumeration may be incomplete in black-box testing; may miss available chains
- Some chains require specific JDK version ranges; modern JDKs (17+) restrict reflective access, breaking some older chains
- RMI/JMX ports may be firewalled; test for exposure via network scan before assuming inaccessibility
- Sandboxed class loaders (OSGi, WAR isolation) may prevent gadget class resolution even if the jar is present

## Related Knowledge

- `java-polymorphic-json` — when the sink is Jackson/Fastjson rather than `ObjectInputStream`
- `rpc-hessian` — when the binary protocol is Hessian/Burlap rather than native serialization
- `signed-state` — when an HMAC/signature wraps the serialized blob
- JEP 290 serialization filtering specification
- `InvalidClassException` with `serialVersionUID` is a version mismatch hint, not a security control

## Tooling

```bash
# Confirm sink (safe — DNS only, no exec)
java -jar ysoserial.jar URLDNS "http://<interactsh-host>" | base64 -w0

# Bounded exec PoC (use only on authorized targets)
java -jar ysoserial.jar CommonsCollections6 "id" | base64 -w0

# Try multiple chains systematically
for chain in CommonsCollections1 CommonsCollections6 CommonsBeanutils1 Spring1 ROME; do
  java -jar ysoserial.jar $chain "ping -c1 <oast-host>" | base64 -w0 > /tmp/${chain}.b64
  echo "Chain: $chain -> /tmp/${chain}.b64"
done
```

Send the payload in the identified parameter/cookie. Observe OAST listener before escalating to exec.