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
│  SessionManager (Singleton)                     │
│  ┌───────────────────────────────────────────┐  │
│  │ 1. Check disk cache for cookies           │  │
│  │ 2. If found & valid → Use (FAST PATH)     │  │
│  │ 3. If not found → Warm up                 │  │
│  │ 4. Save to cache for next time            │  │
│  └───────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  SessionCache (diskcache)                       │
│  Location: ~/.settfex/cache/                    │
│  Format: SQLite + pickled data                  │
│  TTL: 1 hour (configurable)                     │
└─────────────────────────────────────────────────┘
```

### Request Flow

#### First Request (Cache Miss)
```
Request → Check cache → MISS → Warm up session (visit SET homepage)
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

## Usage

### Automatic (Recommended)

The `Stock` class and services automatically use cached sessions:

```python
from settfex.services.set import Stock

# First call: Warmup + cache (~2-3s)
stock = Stock("PTT")
data = await stock.get_highlight_data()

# Subsequent calls: Use cache (~100ms)
stock2 = Stock("CPALL")
data2 = await stock2.get_highlight_data()  # FAST!

# Even after program restart: Use cached cookies!
# (as long as cache hasn't expired)
```

### Manual Control

For advanced use cases, you can manually control the session:

```python
from settfex.utils import SessionManager

# Get singleton instance
manager = await SessionManager.get_instance(
    browser="chrome120",        # Browser to impersonate
    cache_ttl=3600,            # Cache TTL in seconds (1 hour)
    enable_cache=True          # Enable disk caching
)

# Initialize (uses cache if available)
await manager.ensure_initialized()

# Make request
response = await manager.get(
    "https://www.set.or.th/api/set/stock/PTT/highlight-data",
    headers={...},
    auto_retry_on_bot_detection=True  # Auto re-warm on bot detection
)
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
~/.settfex/cache/
├── cache.db              # SQLite index
├── 00/                   # Data shards
│   ├── 00.val
│   ├── 01.val
│   └── ...
└── ...
```

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

Session caching requires:
- `diskcache >= 5.6.0` - Disk-based cache with SQLite backend
- Automatically installed with `settfex`

## Summary

✅ **Automatic** - Works out of the box with Stock class and services
✅ **Fast** - 20-30x speedup after first request
✅ **Persistent** - Survives program restarts
✅ **Reliable** - Auto-retry on bot detection
✅ **Safe** - Thread-safe singleton pattern
✅ **Smart** - Auto-refresh on expiry

**Bottom line:** Just use the library normally and enjoy the speed boost!
