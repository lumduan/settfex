# Session Caching Guide

## Overview

The `settfex` library uses **disk-based session caching** to dramatically improve performance by reusing warmed-up browser sessions across requests and even program restarts.

## Performance Benefits

| Scenario | Time | Speedup |
|----------|------|---------|
| First run (warmup) | ~2-3s | Baseline |
| Cached session | ~100ms | **20-30x faster!** |
| After cache expiry | ~2-3s | Auto re-warm |

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────┐
│  Your Application                               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  SessionManager (Site-Specific Singletons)      │
│  ┌───────────────────────────────────────────┐  │
│  │ Auto-detect the site from the URL host    │  │
│  │ 1. Check disk cache for cookies           │  │
│  │ 2. If found & valid → Use (FAST PATH)     │  │
│  │ 3. If not found → Warm up (per-site)      │  │
│  │ 4. Save to cache for next time            │  │
│  └───────────────────────────────────────────┘  │
│  • One instance per site (cookies are           │
│    per-domain and NOT interchangeable)          │
│  • SET warmup:      https://www.set.or.th       │
│  • TFEX warmup:     https://www.tfex.co.th      │
│  • Settrade warmup: https://www.settrade.com    │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  SessionCache (stdlib sqlite3)                  │
│  Location: ~/.settfex/cache/sessions.sqlite3    │
│  Format: SQLite rows holding JSON text          │
│  TTL: 1 hour (configurable)                     │
│  Keys:                                          │
│    - set_session_chrome120                      │
│    - tfex_session_chrome120                     │
│    - settrade_session_chrome120                 │
└─────────────────────────────────────────────────┘
```

### Request Flow

#### First Request (Cache Miss)
```
Request → Auto-detect site → Check cache → MISS → Warm up session
  (SET or TFEX URL)                                 (visit SET or TFEX homepage)
                                                     ↓
                                                Get Incapsula cookies
                                                     ↓
                                                Save to disk cache
                                                     ↓
                                                Make API call
                                                     ↓
                                                Return data

Time: ~2-3 seconds
```

#### Subsequent Requests (Cache Hit)
```
Request → Check cache → HIT → Load cookies from disk
                               ↓
                          Create session with cookies
                               ↓
                          Make API call
                               ↓
                          Return data

Time: ~100ms (20-30x faster!)
```

#### After Cache Expiry
```
Request → Check cache → EXPIRED → Delete old cache
                                    ↓
                               Warm up new session
                                    ↓
                               Save to cache
                                    ↓
                               Make API call
                                    ↓
                               Return data

Time: ~2-3 seconds (auto-refresh)
```

#### Bot Detection Retry
```
Request → Use cached session → API call → HTTP 403/452 (bot detected!)
                                             ↓
                                        Clear cache
                                             ↓
                                        Warm up fresh session
                                             ↓
                                        Retry API call
                                             ↓
                                        Return data

Automatic - no manual intervention needed!
```

## Dual-Site Support (SET & TFEX)

The session manager maintains **separate cached sessions** for SET and TFEX:

### Automatic Site Detection

The library automatically detects the site from the URL's host:

```python
from settfex.services.set import get_analyst_consensus, get_stock_list
from settfex.services.tfex import get_series_list

# SET API: Warms up with https://www.set.or.th
stock_list = await get_stock_list()

# TFEX API: Warms up with https://www.tfex.co.th
series_list = await get_series_list()

# Settrade API (analyst consensus): Warms up with https://www.settrade.com
consensus = await get_analyst_consensus("GULF")

# Every session is cached separately!
# - ~/.settfex/cache/set_session_chrome120
# - ~/.settfex/cache/tfex_session_chrome120
# - ~/.settfex/cache/settrade_session_chrome120
```

> **Why separate sessions are mandatory, not just tidy:** Incapsula cookies are scoped to a
> domain. A session warmed on `www.set.or.th` is rejected with HTTP 403 on
> `www.settrade.com` (live-probed 2026-08-16), so routing a settrade URL through the SET
> warmup would fail every request.

### Benefits

- **Independent Sessions**: SET, TFEX and Settrade sessions don't interfere with each other
- **Optimal Performance**: Each site gets its own optimized warmup strategy
- **Separate Caching**: Each site maintains its own 1-hour cache
- **No Manual Config**: URL-based detection works automatically

## Usage

### Automatic (Recommended)

All services automatically use the correct cached session:

```python
from settfex.services.set import Stock
from settfex.services.tfex import get_series_list

# SET: First call warms up SET homepage (~2-3s)
stock = Stock("PTT")
data = await stock.get_highlight_data()

# SET: Subsequent calls use cached SET session (~100ms)
stock2 = Stock("CPALL")
data2 = await stock2.get_highlight_data()  # FAST!

# TFEX: First call warms up TFEX homepage (~2-3s)
series = await get_series_list()

# TFEX: Subsequent calls use cached TFEX session (~100ms)
series2 = await get_series_list()  # FAST!

# Even after program restart: Use cached cookies for both sites!
```

### Manual Control

For advanced use cases, you can manually control the session:

```python
from settfex.utils.session_manager import SessionManager

# Get SET session instance
set_manager = await SessionManager.get_instance(
    browser="chrome120",
    warmup_site="set"  # Explicit SET warmup
)

# Get TFEX session instance
tfex_manager = await SessionManager.get_instance(
    browser="chrome120",
    warmup_site="tfex"  # Explicit TFEX warmup
)

# Initialize (uses cache if available)
await set_manager.ensure_initialized()
await tfex_manager.ensure_initialized()

# Make requests
set_response = await set_manager.get(
    "https://www.set.or.th/api/set/stock/list",
    auto_retry_on_bot_detection=True
)

tfex_response = await tfex_manager.get(
    "https://www.tfex.co.th/api/set/tfex/series/list",
    auto_retry_on_bot_detection=True
)
```

### URL-Based Session Selection

Or use the convenience function that auto-detects the site:

```python
from settfex.utils.session_manager import get_session_for_url

# Automatically selects SET warmup
set_session = await get_session_for_url("https://www.set.or.th/api/...")

# Automatically selects TFEX warmup
tfex_session = await get_session_for_url("https://www.tfex.co.th/api/...")
```

### Force Refresh

To force a fresh warmup (bypass cache):

```python
manager = await SessionManager.get_instance()

# Force new warmup (ignore cache)
await manager.ensure_initialized(force_warmup=True)
```

### Disable Caching

To disable caching entirely:

```python
manager = SessionManager(enable_cache=False)
SessionManager._instance = manager

# Now all requests will warmup (slow path)
await manager.ensure_initialized()
```

## Cache Management

### Cache Location

```
~/.settfex/cache/                 # 0700
├── sessions.sqlite3              # 0600 - one row per site/browser, JSON text (since 0.26.1)
├── sessions.sqlite3-wal          # SQLite write-ahead log
├── sessions.sqlite3-shm
└── cache.db, 00/ ...             # only if upgraded from <= 0.26.0: the old diskcache store,
                                  #   never opened again; safe to delete
```

Each row holds a site's cookies **with the domain, host-only flag, path, secure flag and expiry
they were issued for** (`cookie_jar`, since 0.26.3), plus the plain `cookies` name → value map that
0.26.1/0.26.2 read.

### Directory Permissions

The cache directory is created **`0700`** (owner only), and an existing `~/.settfex/cache` left
looser by an earlier version is tightened in place on the next run, with a log line saying so.

The reason: the cached cookies are credentials. Anything that can read them can impersonate your
session, and anything that can write them can plant cookies your process will send.

**Nothing in the cache is unpickled (since 0.26.1).** Before 0.26.1 the store was `diskcache`,
which reads values back with pickle
([CVE-2025-69872](https://nvd.nist.gov/vuln/detail/CVE-2025-69872), no fixed release upstream), so
write access to this directory meant code execution in your process. The store is now stdlib
`sqlite3` holding JSON text: a row that is not a JSON object is a cache miss, never code. The old
`cache.db` is never opened; delete it if you like. The session warms up once after the upgrade.

**Each cookie is restored with the domain it was issued for (since 0.26.3).** Until 0.26.3 the cache
kept only name → value and restored each cookie with no domain. curl_cffi binds such a cookie to the
host of the **first** request that carries it, so the first request after a restore decided where a
site's cookies went, even to another host. Each cookie now comes back with its own attributes
(a real SET warm-up yields `.set.or.th` for the Incapsula cookies and host-only `www.set.or.th` for
`charlot`), so it is sent to that domain and nowhere else. An entry without those attributes,
written by 0.26.2 or older, is treated as a miss: one anonymous warm-up, then the row is rewritten.
A cookie whose domain is not the site's own is refused the same way, so a planted row cannot steer a
site's cookies to another host.

A directory **you** passed as `cache_dir` is treated differently: it is created `0700` if new, but
if it already exists and is group/other-**writable**, settfex logs a warning and
**leaves the mode alone**. A shared cache may be deliberate, and silently breaking that layout
would be worse than telling you about it.

### Cache Statistics

```python
from settfex.utils import get_global_cache

cache = await get_global_cache()
stats = cache.stats()
print(f"Size: {stats['size'] / 1024 / 1024:.2f}MB")
print(f"Items: {stats['count']}")
```

### Clear Cache

```python
from settfex.utils import get_global_cache

cache = await get_global_cache()
cache.clear()  # Delete all cached data
```

Or manually:

```bash
rm -rf ~/.settfex/cache/
```

## Configuration

### Environment-Specific Settings

**Development:**
```python
# Short TTL for frequent changes
manager = SessionManager(cache_ttl=300)  # 5 minutes
```

**Production:**
```python
# Longer TTL for stability
manager = SessionManager(cache_ttl=7200)  # 2 hours
```

**Testing:**
```python
# Disable cache for fresh sessions
manager = SessionManager(enable_cache=False)
```

### Custom Cache Directory

```python
from pathlib import Path

manager = SessionManager(
    cache_dir=Path("/tmp/my_cache")
)
```

> ⚠️ A world-writable location such as a bare `/tmp` path is exactly the case
> [CVE-2025-69872](https://nvd.nist.gov/vuln/detail/CVE-2025-69872) describes — another local
> account can drop a pickle into the cache and run code in your process. settfex warns when the
> directory you pass is group/other-writable but will not change permissions you chose. Prefer a
> directory only your account can write to.

## Advanced Features

### Auto-Retry on Bot Detection

The SessionManager automatically detects bot protection (HTTP 403/452) and:
1. Clears the cached cookies
2. Warms up a fresh session
3. Retries the request once

No manual intervention needed!

### Thread Safety

Both `SessionCache` and `SessionManager` are thread-safe:
- Uses `asyncio.Lock` for concurrent access
- Singleton pattern ensures single instance
- Disk cache uses SQLite (thread-safe by default)

### Cache Expiration

Cached sessions automatically expire after TTL:
- Default: 1 hour (3600 seconds)
- Configurable per instance
- Auto-refresh on expiry

### Graceful Degradation

If cache operations fail:
- Falls back to warmup (slow path)
- Logs errors but doesn't fail request
- Continues without caching

## Best Practices

### ✅ Do

1. **Use default caching** - It just works!
   ```python
   stock = Stock("PTT")  # Caching enabled by default
   ```

2. **Share SessionManager** - Use singleton pattern
   ```python
   manager = await SessionManager.get_instance()
   ```

3. **Set appropriate TTL** - Balance freshness vs performance
   ```python
   manager = SessionManager(cache_ttl=3600)  # 1 hour
   ```

4. **Let auto-retry handle failures** - Don't catch 403/452 yourself
   ```python
   # Auto-retry enabled by default
   response = await manager.get(url, auto_retry_on_bot_detection=True)
   ```

### ❌ Don't

1. **Don't create multiple SessionManager instances**
   ```python
   # ❌ Bad: Creates new session each time
   for symbol in symbols:
       manager = SessionManager()  # Wrong!

   # ✅ Good: Reuse singleton
   manager = await SessionManager.get_instance()
   for symbol in symbols:
       await manager.get(url)
   ```

2. **Don't disable caching without reason**
   ```python
   # ❌ Bad: Loses performance benefits
   manager = SessionManager(enable_cache=False)

   # ✅ Good: Use default (cached)
   manager = await SessionManager.get_instance()
   ```

3. **Don't forget to handle auto-retry errors**
   ```python
   # ❌ Bad: No error handling
   response = await manager.get(url)

   # ✅ Good: Handle failures after retry
   try:
       response = await manager.get(url)
       if response.status_code != 200:
           logger.error(f"Failed: {response.status_code}")
   except Exception as e:
       logger.error(f"Request failed: {e}")
   ```

## Troubleshooting

### Cache Not Working?

Check logs:
```python
from loguru import logger

logger.info("Starting request...")
# Look for: "✓ Loaded session from cache" vs "Warming up session"
```

### Bot Detection Despite Cache?

1. Check cache age: May be expired
2. Try force refresh: `ensure_initialized(force_warmup=True)`
3. Check SET website status: May have changed protection

### Cache Taking Too Much Space?

```python
# Check size
cache = await get_global_cache()
print(cache.stats())

# Clear if needed
cache.clear()
```

### Performance Not Improving?

1. Verify cache is enabled: `enable_cache=True` (default)
2. Check TTL: Long enough? `cache_ttl=3600`
3. Look for "Cache HIT" in logs
4. Profile with demo script: `python scripts/demo_session_cache.py`

## Benchmarks

Real-world performance (100 requests):

| Configuration | Time | Requests/sec |
|---------------|------|--------------|
| No cache (warmup each time) | ~250s | 0.4 req/s |
| With cache (after first) | ~12s | 8.3 req/s |
| **Improvement** | **20x faster** | **20x throughput** |

Single request comparison:

| Scenario | Time | vs Baseline |
|----------|------|-------------|
| First request (warmup) | 2.3s | 1x |
| Cached request | 0.09s | **25x faster** |
| Expired cache (re-warm) | 2.4s | 1x |

## Dependencies

Session caching uses only the standard library (`sqlite3`, `json`). There is no third-party
cache dependency since 0.26.1, which dropped `diskcache` and its pickle advisory.

## Summary

✅ **Automatic** - Works out of the box with Stock class and services
✅ **Fast** - 20-30x speedup after first request
✅ **Persistent** - Survives program restarts
✅ **Reliable** - Auto-retry on bot detection
✅ **Safe** - Thread-safe singleton pattern
✅ **Smart** - Auto-refresh on expiry

**Bottom line:** Just use the library normally and enjoy the speed boost!
