import logging

import aiohttp
import aiohttp.web
import asab.web.auth

import asab.web.rest

#

L = logging.getLogger(__name__)

#


class ProxyWebHandler:

	def __init__(self, app, discovery_service):
		self.App = app
		self.DiscoveryService = discovery_service

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
		value = request.match_info["value"]
		proxy_path = request.match_info["proxy_path"]

		# Locate URLs using the key-value pair
		# TODO: Is this safe?
		urls = await self.DiscoveryService.locate(**{key: value})

		if not urls:
			return asab.web.rest.json_response(
				request, {"result": "NOT-FOUND"}, status=404
			)

		# Extract request details
		method = request.method
		query_params = request.query_string
		body = await request.read()
		headers = {key: value for key, value in request.headers.items()}

		# Forward the request to the first available URL
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
						data=body,
					) as resp:

						# Forward the response back to the client
						payload = await resp.read()

						return aiohttp.web.Response(
							body=payload,  # Use the raw payload as the body
							status=resp.status,  # Forward the status code from the proxied response
							headers=resp.headers,  # Forward the headers from the proxied response
						)

			except aiohttp.client_exceptions.ClientConnectorError:
				# If this url could not be connected to, try another one
				continue

		return asab.web.rest.json_response(
			request, {"result": "NOT-FOUND"}, status=404
		)
