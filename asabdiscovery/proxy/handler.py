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


class ProxyWebHandler:

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


	async def proxy_by_key(self, request):
		key = request.match_info["key"]

		# For safety purposes
		if key not in self.ProxyAllowedKeys:
			return asab.web.rest.json_response(
				request, {"result": "KEY-NOT-ALLOWED"}, status=405
			)

		value = request.match_info["value"]
		proxy_path = request.match_info["proxy_path"]

		# Locate URLs using the key-value pair
		urls = await self.DiscoveryService.locate(**{key: value})

		if not urls:
			return asab.web.rest.json_response(
				request, {"result": "NOT-FOUND"}, status=404
			)

		# Extract request details
		method = request.method
		query_params = request.query_string
		headers = {key: value for key, value in request.headers.items()}

		# Use streaming for the request body
		# TODO: This needs to be tested
		body_stream = request.content.iter_any()

		for url in urls:
			url_with_endpoint = f"{url}/{proxy_path}"

			if query_params:
				url_with_endpoint = f"{url_with_endpoint}?{query_params}"

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
						return response

			except aiohttp.client_exceptions.ClientConnectorError:
				# If this url could not be connected to, try another one
				continue

		return asab.web.rest.json_response(
			request, {"result": "NOT-FOUND"}, status=404
		)
