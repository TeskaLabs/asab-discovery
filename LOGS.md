# asab-discovery Log Reference

Operational log messages emitted by this service. Log lines include the Python module name as the logger (for example `asabdiscovery.proxy.handler`) and optional structured fields in `[sd ...]`.

Severity guide:

- **CRITICAL** — application stops or cannot start
- **ERROR** — proxy request failed because no reachable backend could be contacted
- **WARNING** — request rejected or degraded; service remains healthy
- **NOTICE** — important lifecycle events (visible in non-verbose mode)
- **INFO / DEBUG** — verbose diagnostics only

---

## CRITICAL

This service does not emit application-level `CRITICAL` logs. Unhandled startup failures are logged by the ASAB framework and cause the process to exit.

---

## ERROR

| Module | Message summary | Structured fields | When it happens | Operator action |
|--------|-----------------|-------------------|-----------------|-----------------|
| `asabdiscovery.proxy.handler` | Discovery proxy could not reach any backend instance for the requested service | `method`, `path`, `remote`, `request_id` (when present), `locate_key`, `locate_value`, `proxy_path`, `tenant`, `attempted_urls`, `attempts_total`, `exception_type`, `http_status`, `result` | Discovery returned one or more backend URLs, but every connection attempt failed with `ClientConnectorError` | Verify backend hosts are running and reachable from this pod/container; check firewall and advertised `web` ports in ZooKeeper; inspect traceback for the last connection error |

---

## WARNING

| Module | Message summary | Structured fields | When it happens | Operator action |
|--------|-----------------|-------------------|-----------------|-----------------|
| `asabdiscovery.app` | ZooKeeper is not configured; service discovery will not load instance advertisements | _(none)_ | Application starts without a `[zookeeper]` configuration section | Add `[zookeeper]` with `servers=...` if this service should discover cluster instances |
| `asabdiscovery.proxy.handler` | Discovery proxy request rejected because the locate key is not allowed | `method`, `path`, `remote`, `request_id` (when present), `locate_key`, `locate_value`, `proxy_path`, `tenant`, `allowed_locate_keys`, `http_status`, `result` | Client used a locate key outside `proxy:allowed_keys` | Expected client/config mismatch; update `proxy:allowed_keys` or fix the request URL |
| `asabdiscovery.proxy.handler` | No service instances were found in the discovery registry | `method`, `path`, `remote`, `request_id` (when present), `locate_key`, `locate_value`, `proxy_path`, `tenant`, `http_status`, `result` | `DiscoveryService.locate()` returned no URLs for the requested key/value | Verify the target service is running and registered in ZooKeeper; confirm `[zookeeper]` matches other cluster services |
| `asabdiscovery.proxy.handler` | Discovery proxy could not connect to a backend instance; trying the next discovered instance | `method`, `path`, `remote`, `request_id` (when present), `locate_key`, `locate_value`, `proxy_path`, `tenant`, `target_url`, `backend_url`, `attempt`, `attempts_total`, `exception_type`, `result` | A single backend URL is unreachable; additional discovered instances may still be tried | Check reachability of the listed `backend_url`; may be transient if failover succeeds |

---

## NOTICE (selected)

| Module | Message summary | Structured fields |
|--------|-----------------|-------------------|
| `asabdiscovery.app` | ZooKeeper integration enabled for service discovery | `zookeeper_servers` |
| `asabdiscovery.app` | ASAB Discovery application initialized and ready to accept proxy requests | `web_listen`, `zookeeper_enabled` |
| `asabdiscovery.proxy.handler` | Discovery proxy route registered | `allowed_locate_keys`, `allowed_locate_key_count` |

---

## INFO / DEBUG (selected)

| Module | Message summary | Structured fields |
|--------|-----------------|-------------------|
| `asabdiscovery.proxy.handler` | Discovery proxy request forwarded successfully to a backend instance | `method`, `path`, `remote`, `request_id` (when present), `locate_key`, `locate_value`, `proxy_path`, `tenant`, `target_url`, `backend_url`, `attempt`, `attempts_total`, `backend_status`, `result` |
