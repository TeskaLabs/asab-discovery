# CHANGELOG

## v25.16

### Features
- OpenAPI documentation for the discovery proxy endpoint, available at `GET /doc`

### Refactoring
- Structured logging for application startup, proxy route registration, and proxied requests
- Improved log messages for backend connection failures, missing discovery registrations, and disallowed locate keys to simplify troubleshooting
