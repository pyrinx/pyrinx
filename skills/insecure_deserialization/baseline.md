# Insecure Deserialization

## Definition

Insecure deserialization occurs when an application passes attacker-controlled byte streams or structured blobs to language-native unmarshal functions without sufficient validation, type restriction, or integrity protection. The deserialization process reconstructs object graphs from serialized data, and in many runtimes this reconstruction can invoke arbitrary code through magic methods, gadget chains, or type-polymorphism mechanisms.

## Security Property

**Integrity of object graph reconstruction**: Only trusted, schema-conformant data should be deserialized into live objects. Attacker-controlled types, class names, or raw byte streams must never reach a deserialization sink without verified integrity (cryptographic HMAC or equivalent) and strict type allowlisting.

## Core Concepts

- **Serialization format**: The wire encoding of an object graph — native binary (Java, .NET, Ruby), text-based (PHP), or structured data with embedded type hints (JSON with `@type`, YAML with `!!` tags, Hessian).
- **Deserialization sink**: The call that reconstructs live objects — `ObjectInputStream.readObject()`, `pickle.loads()`, `unserialize()`, `BinaryFormatter.Deserialize()`, `Marshal.load()`.
- **Magic methods / lifecycle hooks**: Language-level callbacks invoked automatically during deserialization — Java `readObject`/`readResolve`, PHP `__wakeup`/`__destruct`/`__toString`, Python `__reduce__`, Ruby `marshal_load`.
- **Gadget chain**: A sequence of existing classes on the application classpath that, when deserialized in a crafted order, chains method calls to reach a dangerous primitive (exec, file write, SSRF).
- **Type confusion / polymorphic deserialization**: When a deserializer accepts an attacker-chosen class name embedded in the payload (`$type`, `@class`, `!!python/object`), enabling instantiation of arbitrary types.
- **OAST (Out-of-Band Application Security Testing)**: DNS or HTTP callback technique to confirm a sink is reached without executing destructive commands — the canonical safe oracle for deserialization.

## Attack Surface

**Formats by runtime**
- Java: native serialization (`ac ed 00 05`), XStream (XML), Jackson/Fastjson/Gson polymorphic JSON, SnakeYAML (`!!` tags), Hessian/Burlap (binary RPC), Kryo
- Python: `pickle` / `cPickle`, `yaml.load` (unsafe loader), `marshal`, `shelve`
- PHP: `unserialize()`, Phar metadata deserialization via stream wrappers
- .NET: `BinaryFormatter`, `LosFormatter`, `Json.NET` with `TypeNameHandling`, ASP.NET ViewState, `NetDataContractSerializer`
- Ruby: `Marshal.load`, `YAML.load` (Psych with unsafe tags)
- Node.js: `node-serialize`, legacy `unserialize.js` (prototype pollution overlap — scope separately)

**Transport / container locations**
- HTTP cookies, session tokens, `Authorization` headers
- POST body parameters, hidden form fields, base64-encoded query strings
- WebSocket binary frames, message queue payloads, RMI/JMX endpoints
- File uploads processed server-side, cache entries, database columns storing serialized blobs

## Input / Data Flow

```
Attacker input
    → transport layer (HTTP, queue, file, socket)
    → optional encoding/compression (base64, gzip, hex)
    → optional integrity check (HMAC, signature — may be absent or weak)
    → deserialization sink (readObject, pickle.loads, unserialize, …)
    → object graph reconstruction (constructor / magic methods / setters)
    → gadget chain execution → dangerous primitive (exec, JNDI lookup, file write)
```

Identify each stage explicitly; controls at one stage do not necessarily protect later stages.

## Vulnerability Indicators

**Black-box signals**
- Response/cookie/parameter contains base64 with magic-byte prefixes:
  - Java native: `rO0` (base64 of `ac ed 00 05`)
  - PHP: decoded string starts with `O:`, `a:`, `s:`
  - .NET BinaryFormatter: `AAEAAAD/////` prefix pattern
- `Content-Type: application/x-java-serialized-object` or custom binary MIME types
- Stack traces referencing `ObjectInputStream`, `ClassNotFoundException`, `readObject`, `InvalidClassException`
- Responses change shape when base64 blob is truncated or corrupted (deserialization error vs. generic error)

**White-box signals**
```
pickle.loads        yaml.load(          ObjectInputStream   readObject(
unserialize(        __wakeup            __destruct          BinaryFormatter
TypeNameHandling    Marshal.load        HessianInput        Hessian2Input
XStream.fromXML     SnakeYAML().load    JsonTypeInfo        enableDefaultTyping
```

## Preconditions

1. Application passes user-influenced data to a deserialization sink (directly or via second-order path).
2. No allowlist restricting deserialized class types, OR allowlist is bypassable.
3. Classpath / installed packages contain gadget classes reachable through the deserializer.
4. No verified cryptographic integrity check preventing payload tampering, OR the check is weak / bypassable.

## Common Variants

| Variant | Key Mechanism |
|---------|---------------|
| Java native gadget chain | `ObjectInputStream` + classpath gadgets (Commons Collections, Spring, etc.) |
| Polymorphic JSON (Jackson, Fastjson) | Attacker-controlled `@class`/`@type` field → arbitrary constructor/setter |
| Python pickle RCE | `__reduce__` executes arbitrary callable during unpickling |
| PHP object injection | `unserialize` triggers `__wakeup`/`__destruct` POP chains |
| Phar deserialization | PHP stream wrapper triggers metadata unserialize on file operations |
| .NET BinaryFormatter | Full object graph deserialization → ysoserial.net gadget chains |
| .NET ViewState forgery | Disabled or weak MAC → forged ViewState with gadget payload |
| Ruby Marshal | `Marshal.load` on user data → Rails/Devise gadget chains |
| Hessian/Burlap RPC | Binary RPC format reaches Java gadgets via `HessianInput` |
| Signed blob bypass | Weak HMAC secret or algorithm confusion → forge tampered payload |
| Second-order deserialization | Payload stored, deserialized later by background job or admin action |
| YAML unsafe load | `yaml.load` / SnakeYAML `!!` tags → code execution via type constructor |

## Impact Model

- **Remote code execution**: Attacker executes OS commands on the server process.
- **Authentication bypass**: Forged session/role objects grant elevated privileges without credentials.
- **Privilege escalation**: Manipulated field values (admin flags, role arrays) in deserialized session.
- **SSRF / JNDI pivot**: Object construction triggers outbound lookup to attacker-controlled endpoint.
- **Denial of service**: Billion-laughs-style recursive structures exhaust heap; intentional `ClassNotFoundException` loops.
- **File write / path traversal**: Gadgets writing attacker-controlled content to arbitrary paths.

## Evidence Model

Proof of exploitability requires demonstrating:
1. Attacker-controlled data reaches the deserialization sink.
2. The sink reconstructs an object graph under attacker influence.
3. Impact is demonstrated via:
   - **Safe oracle first**: DNS/HTTP OAST callback (`URLDNS` chain, interactsh) — no command execution.
   - **Bounded execution PoC**: `id`, `whoami`, `sleep 5`, `ping -c 3` — minimal, reversible.
4. Exact injection point (parameter name, cookie name, header, content-type), encoding, and gadget chain documented.
5. On a fixed instance or with a correct allowlist, the identical payload fails safely.

## False Positives

- Data is JSON/XML parsed into primitive types only; no polymorphic type loading.
- Deserialization is preceded by a verified HMAC/signature using a secret unavailable to the attacker.
- Only an allowlisted set of simple value types is permitted; no object instantiation beyond schema types.
- `yaml.safe_load` used instead of `yaml.load`; SnakeYAML `SafeConstructor` enforced.
- Deserialization runs inside an isolated sandbox with no exec/network/filesystem primitives (verify sandbox escape surface thoroughly before dismissing).
- Error references a serialization class, but the user input does not actually reach the unmarshal call (dead code, unreachable branch).

## Limitations

- Gadget chain availability depends on the exact classpath/package versions deployed; wrong chain fails silently or produces errors.
- OAST callbacks may be blocked by egress filtering — absence of a callback does not prove the sink is not reached.
- Second-order sinks require knowledge of the trigger (batch job, admin action, cache warm) and may have long delays.
- Sandboxed or allowlisted deserializers require deeper gadget research; absence of known chains does not prove safety.
- Some JNDI-based gadget paths depend on JDK version, provider configuration, and local factory availability — model each stage separately.

## Specialist Approach Signals

Select the appropriate approach file based on:

| Signal | Approach |
|--------|----------|
| Java app, binary blob, `rO0` prefix, `readObject` sink | `java-native` |
| Java app, JSON with `@class`/`@type`/`@JsonTypeInfo`, Jackson/Fastjson | `java-polymorphic-json` |
| Python app, `pickle.loads`, base64 blob, cookie/session | `python-pickle` |
| Python/any app, YAML parsing with `yaml.load`, `!!` tags | `python-yaml` |
| PHP app, `unserialize()`, POP chain suspects | `php-object` |
| .NET app, `BinaryFormatter`, `LosFormatter`, WCF | `dotnet-binaryformatter` |
| .NET app, Json.NET `TypeNameHandling`, `$type` field | `dotnet-jsonnet` |
| Ruby/Rails app, `Marshal.load`, session cookie blob | `ruby-marshal` |
| Java RPC endpoint, Hessian/Burlap binary frames | `rpc-hessian` |
| Signed/MAC-protected session blob, algorithm confusion suspects | `signed-state` |
| Payload stored and triggered later, admin/batch/cache context | `second-order` |

## Terminology

| Term | Meaning |
|------|---------|
| Gadget | Existing class whose methods, when invoked during deserialization, advance toward a dangerous primitive |
| POP chain | Property-Oriented Programming chain — PHP-specific gadget chain through magic methods |
| OAST | Out-of-Band Application Security Testing — DNS/HTTP callback to confirm sink reachability without exec |
| Magic method | Language-defined lifecycle method auto-invoked during deserialization (`__reduce__`, `readObject`, `__wakeup`) |
| TypeNameHandling | Json.NET option controlling whether `$type` fields are respected for polymorphic deserialization |
| `enableDefaultTyping` | Jackson API that enables polymorphic type resolution globally — insecure on untrusted input |
| JNDI | Java Naming and Directory Interface — a lookup API that can be triggered by object construction in some gadget paths |
| ViewState | ASP.NET mechanism serializing page state to a hidden field; deserialized server-side on postback |
| Phar | PHP archive format whose metadata is deserialized when a `phar://` stream wrapper triggers a file operation |
| Hessian | Binary serialization protocol for Java RPC; distinct from native Java serialization but reaches the same gadget classes |