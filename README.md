# asab-discovery

Discovery microservice that forwards HTTP requests to cluster microservices.

In a distributed cluster, services are started, stopped, scaled, and moved across nodes.
Their host names and ports change over time, so hard-coding backend addresses in every client does not scale.
**Service discovery** solves this: each microservice advertises itself when it starts and de-advertises when it stops.
Other components then look up a logical identifier — such as `service_id` or `instance_id` — and receive the current list of reachable instances.

That indirection is what makes a cluster operable.
Operators can roll out new versions, replace failed nodes, or add capacity without reconfiguring every caller.
Clients talk to a stable name; the discovery layer maps it to whatever is running right now.
When several instances exist, callers can fail over to the next one if the first is unreachable.

In the [ASAB](https://github.com/TeskaLabs/asab) ecosystem, **[Apache ZooKeeper](https://zookeeper.apache.org/)** is the shared coordination store for the cluster.
Running services advertise themselves under a well-known path; discovery consumers watch that registry and refresh their view as instances come and go.

This repository provides the HTTP proxy for that process.
Clients call a single well-known endpoint instead of knowing each service's host and port.
The proxy resolves a locate key (for example `service_id`) to one or more backend instances and forwards the request with the same method, headers, query string, and body.
Responses are streamed back to the caller.

This microservice is tightly bound to the [ASAB DiscoveryService](https://github.com/TeskaLabs/asab/blob/master/asab/api/discovery.py), which implements the discovery and advertisement logic on top of ZooKeeper and resolves locate keys to backend URLs.


## Running


### Local development

Requires Python 3.9+ and [ASAB](https://github.com/TeskaLabs/asab).

```bash
pip install asab
python3 asab-discovery.py -c etc/asab-discovery.conf
```


### Docker

```bash
docker build -t asab-discovery .
docker run -p 8897:8897 -v /path/to/asab-discovery.conf:/conf/asab-discovery.conf asab-discovery
```

The container expects configuration at `/conf/asab-discovery.conf`.


## Operations

Structured logging covers application startup, proxy route registration, and proxied requests.
See [LOGS.md](LOGS.md) for message reference and troubleshooting.

Example Bruno requests are in [docs/bruno/](docs/bruno/).


## Configuration

Default listen port is **8897**. Example configuration file (`etc/asab-discovery.conf`):

```ini
[web]
listen=8897

[zookeeper]
servers=zookeeper-1:2181

[proxy]
allowed_keys=service_id,instance_id,baseline_id,correlator_id
```

### Allowed locate keys

By default: `service_id`, `instance_id`, `baseline_id`, `correlator_id`.

The list is configurable via `[proxy] allowed_keys` (comma-separated).


## License

See [LICENSE](LICENSE).
