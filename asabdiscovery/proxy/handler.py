import logging

import aiohttp
import aiohttp.web

import asab
import asab.web.auth
import asab.web.rest

#

L = logging.getLogger(__name__)

#

asab.Config.add_defaults({
	"proxy": {
		# Allowed keys for the discovery locate function inside the proxy separated by ,
		"allowed_keys": "service_id,instance_id,baseline_id,correlator_id",
	}
})


def _request_struct_data(request, **extra):
	"""
	Build structured log fields common to proxy request handling.
	"""
	struct_data = {
		"endpoint": "GET|POST|PUT|DELETE /~/{key}/{value}/{proxy_path}",
		"method": request.method,
		"path": request.path,
		"remote": request.remote,
	}

	for header_name in ("X-Request-ID", "X-Correlation-ID", "X-Trace-ID"):
		header_value = request.headers.get(header_name)
		if header_value is not None:
			struct_data["request_id"] = header_value
			break

	struct_data.update(extra)
	return struct_data


def _tenant_from_proxy_path(proxy_path):
	if not proxy_path:
		return None
	return proxy_path.split("/", 1)[0] or None


def _sanitize_url_for_log(url):
	"""
	Return a URL safe for structured logging by removing the query string.
	"""
	return url.partition("?")[0]


class ProxyWebHandler:
	"""
	Discovery proxy — forward HTTP requests to cluster microservices.

	---
	tags: ['Discovery Proxy']
	"""

	def __init__(self, app, discovery_service):
		self.App = app
		self.DiscoveryService = discovery_service
		self.ProxyAllowedKeys = asab.Config["proxy"]["allowed_keys"].split(',')

		web_app = app.WebContainer.WebApp

		# Add the proxy endpoint(s)
		# Example: /~/service_id/<service_id>/<tenant>/<object>/<method>
		web_app.router.add_route(
			'*',  # Accept all HTTP methods (GET, POST, etc.)
			r"/~/{key}/{value}/{proxy_path:.*}",
			self.proxy_by_key,
		)

		L.log(
			asab.LOG_NOTICE,
			"Discovery proxy route registered. "
			"Incoming requests matching /~/{key}/{value}/... will be forwarded to discovered service instances.",
			struct_data={
				"allowed_locate_keys": self.ProxyAllowedKeys,
				"allowed_locate_key_count": len(self.ProxyAllowedKeys),
			},
		)


	async def proxy_by_key(self, request):
		"""
		Forward a request to a discovered microservice instance.

		Use this endpoint to call any HTTP API on a service registered in the
		cluster discovery registry (ZooKeeper). The discovery service resolves
		`key` and `value` to one or more backend instances, then forwards the
		request with the same HTTP method, headers, query string, and body.
		The response from the backend is streamed back to the caller.

		**URL pattern**

		```
		/~/{key}/{value}/{proxy_path}
		```

		- `key` — locate parameter name (see allowed keys below).
		- `value` — identifier to look up (for example a `service_id` or `instance_id`).
		- `proxy_path` — path appended to the backend base URL (often starts with a tenant name).

		**Allowed locate keys**

		By default: `service_id`, `instance_id`, `baseline_id`, `correlator_id`.
		The list is configurable via `[proxy] allowed_keys` in the service configuration.

		**Examples**

		Call the ASAB Config service by `service_id`:

		```
		GET /~/service_id/asab-config/mytenant/asab/v1/config
		```

		Call a specific instance by `instance_id`:

		```
		GET /~/instance_id/asab-config-1/mytenant/api/status
		```

		POST JSON to a backend API:

		```
		POST /~/service_id/lmio-receiver/mytenant/receive
		Content-Type: application/json

		{"event": "login", "user": "alice"}
		```

		**Failover**

		When multiple instances match the locate key, the proxy tries them in order.
		If a backend is unreachable, the next discovered instance is attempted.
		The caller receives the first successful backend response.

		**Error responses from the proxy**

		When the proxy itself cannot forward the request, it returns JSON:

		```json
		{"result": "KEY-NOT-ALLOWED"}
		```

		```json
		{"result": "NOT-FOUND"}
		```

		---
		tags: ['Discovery Proxy']
		parameters:
			- name: key
			  in: path
			  required: true
			  description: Locate parameter name used to find backend instances.
			  schema:
			    type: string
			    enum: [service_id, instance_id, baseline_id, correlator_id]
			- name: value
			  in: path
			  required: true
			  description: Identifier value for the chosen locate key (for example `asab-config` when key is `service_id`).
			  schema:
			    type: string
			    example: asab-config
			- name: proxy_path
			  in: path
			  required: true
			  description: Remainder of the URL path forwarded to the backend after the locate segment. Often starts with a tenant name.
			  schema:
			    type: string
			    example: mytenant/asab/v1/config
		responses:
			'200':
				description: Successful response streamed from the backend service. Content type and body depend on the target API.
			'404':
				description: No matching service instance was found, or every discovered instance was unreachable.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: NOT-FOUND
			'405':
				description: The locate key in the URL is not allowed by the proxy configuration.
				content:
					application/json:
						schema:
							type: object
							properties:
								result:
									type: string
									example: KEY-NOT-ALLOWED
		"""
		key = request.match_info["key"]
		value = request.match_info["value"]
		proxy_path = request.match_info["proxy_path"]
		tenant = _tenant_from_proxy_path(proxy_path)

		# For safety purposes
		if key not in self.ProxyAllowedKeys:
			L.warning(
				"Discovery proxy request rejected because the locate key is not allowed. "
				"This is expected when a client uses a disallowed key and does not indicate a service failure. "
				"Verify proxy:allowed_keys and the requested URL.",
				struct_data=_request_struct_data(
					request,
					locate_key=key,
					locate_value=value,
					proxy_path=proxy_path,
					tenant=tenant,
					allowed_locate_keys=self.ProxyAllowedKeys,
					http_status=405,
					result="KEY-NOT-ALLOWED",
				),
			)
			return asab.web.rest.json_response(
				request,
				{
					"result": "KEY-NOT-ALLOWED"
				},
				status=405
			)

		# Locate URLs using the key-value pair
		urls = await self.DiscoveryService.locate(**{key: value})

		if not urls:
			L.warning(
				"No service instances were found in the discovery registry for the requested locate key and value. "
				"The proxy cannot forward this request. "
				"Verify that the target service is running, registered in ZooKeeper, and that [zookeeper] configuration matches the cluster.",
				struct_data=_request_struct_data(
					request,
					locate_key=key,
					locate_value=value,
					proxy_path=proxy_path,
					tenant=tenant,
					http_status=404,
					result="NOT-FOUND",
				),
			)
			return asab.web.rest.json_response(
				request,
				{
					"result": "NOT-FOUND"
				},
				status=404
			)

		# Extract request details
		method = request.method
		query_params = request.query_string
		headers = {hdr_key: hdr_value for hdr_key, hdr_value in request.headers.items()}

		# Use streaming for the request body
		body_stream = request.content.iter_any()

		urls_list = list(urls)
		attempted_urls = []
		last_exception = None
		for attempt_index, url in enumerate(urls_list, start=1):
			url_with_endpoint = f"{url}/{proxy_path}"

			if query_params:
				url_with_endpoint = f"{url_with_endpoint}?{query_params}"

			url_for_log = _sanitize_url_for_log(url_with_endpoint)
			attempted_urls.append(url_for_log)

			try:

				async with aiohttp.ClientSession() as session:

					async with session.request(
						method=method,
						url=url_with_endpoint,
						headers=headers,
						data=body_stream,
						proxy=None,  # Explicitly disable proxy for this request

					) as resp:
						# Stream the response back to the client
						response = aiohttp.web.StreamResponse(
							status=resp.status, headers=resp.headers
						)

						await response.prepare(request)

						async for chunk in resp.content.iter_chunked(1024):
							await response.write(chunk)

						await response.write_eof()

						L.info(
							"Discovery proxy request forwarded successfully to a backend instance.",
							struct_data=_request_struct_data(
								request,
								locate_key=key,
								locate_value=value,
								proxy_path=proxy_path,
								tenant=tenant,
								target_url=url_for_log,
								backend_url=url,
								attempt=attempt_index,
								attempts_total=len(urls_list),
								backend_status=resp.status,
								result="OK",
							),
						)
						return response

			except aiohttp.client_exceptions.ClientConnectorError as e:
				# If this url could not be connected to, try another one
				last_exception = e
				L.debug(
					"Discovery proxy could not connect to a backend instance; trying the next discovered instance if available. "
					"This may indicate a temporarily unreachable host or stale discovery data.",
					struct_data=_request_struct_data(
						request,
						locate_key=key,
						locate_value=value,
						proxy_path=proxy_path,
						tenant=tenant,
						target_url=url_for_log,
						backend_url=url,
						attempt=attempt_index,
						attempts_total=len(urls_list),
						exception_type=e.__class__.__name__,
						result="BACKEND-UNREACHABLE",
					),
				)
				continue

		if last_exception is not None:
			L.error(
				"Discovery proxy could not reach any backend instance for the requested service. "
				"Discovered instances exist but all connection attempts failed. "
				"Verify backend host reachability, firewall rules, and that advertised web ports in ZooKeeper are correct.",
				exc_info=(type(last_exception), last_exception, last_exception.__traceback__),
				struct_data=_request_struct_data(
					request,
					locate_key=key,
					locate_value=value,
					proxy_path=proxy_path,
					tenant=tenant,
					attempted_urls=attempted_urls,
					attempts_total=len(urls_list),
					exception_type=last_exception.__class__.__name__,
					http_status=404,
					result="NOT-FOUND",
				),
			)

		return asab.web.rest.json_response(
			request,
			{
				"result": "NOT-FOUND"
			},
			status=404
		)
