# CHANGELOG

## v26.45

### Features

- Skip JWT on /export path for signed downloads

## v26.37

### Infrastructure
- Upgrade container base image from Alpine 3.18 to Alpine 3.22 ([#4](https://github.com/TeskaLabs/asab-discovery/pull/4))
- Update runtime to Python 3.12 and adjust pip installation for system packages ([#4](https://github.com/TeskaLabs/asab-discovery/pull/4))
- Remove upper version constraint on pygit2 in Dockerfile

## v26.28

### Features
- OpenAPI documentation for the discovery proxy endpoint, available at `GET /doc`

### Refactoring
- Structured logging for application startup, proxy route registration, and proxied requests
- Improved log messages for backend connection failures, missing discovery registrations, and disallowed locate keys to simplify troubleshooting
