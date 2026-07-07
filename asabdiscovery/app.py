import logging

import asab.api
import asab.web
import asab.web.rest
import asab.zookeeper
import asab.proactor
import asab.metrics

import asab.api.discovery

from .proxy.handler import ProxyWebHandler


L = logging.getLogger(__name__)


asab.Config.add_defaults({
	"web": {
		"listen": "8897",  # Well-known port of asab discovery
	},
	"auth": {
		"public_keys_url": "http://seacat-auth.service_id.asab/.well-known/jwks.json"
	},
})


class ASABDiscoveryApplication(asab.Application):
	"""
	ASAB Discovery — HTTP proxy for cluster microservices.

	The discovery service reads instance advertisements from ZooKeeper and
	forwards client requests to the matching backend. Use the `/~/…` proxy
	endpoint to call any registered microservice without knowing its host
	and port.

	Interactive API reference is available at `GET /doc`.
	"""

	def __init__(self):
		super().__init__(modules=[
			asab.proactor.Module,
			asab.web.Module,
			asab.zookeeper.Module,
			asab.metrics.Module,
		])


	async def initialize(self):
		# Initialize the web service
		self.WebService = self.get_service("asab.WebService")
		self.WebContainer = asab.web.WebContainer(self.WebService, "web")
		self.WebContainer.WebApp.middlewares.append(asab.web.rest.JsonExceptionMiddleware)

		self.ProactorService = self.get_service("asab.ProactorService")

		# Initialize Sentry.io
		if asab.Config.has_section("sentry"):
			import asab.sentry as asab_sentry
			self.SentryService = asab_sentry.SentryService(self)

		# Initialize ZooKeeper Service
		if 'zookeeper' in asab.Config.sections():
			self.ZooKeeperService = self.get_service("asab.ZooKeeperService")
			self.ZooKeeperContainer = asab.zookeeper.ZooKeeperContainer(self.ZooKeeperService, 'zookeeper')
			L.log(
				asab.LOG_NOTICE,
				"ZooKeeper integration enabled for service discovery. "
				"Instance advertisements will be read from the configured ZooKeeper cluster.",
				struct_data={
					"zookeeper_servers": asab.Config.get("zookeeper", "servers", fallback=""),
				},
			)

		else:
			self.ZooKeeperContainer = None
			L.warning(
				"ZooKeeper is not configured; service discovery will not load instance advertisements from ZooKeeper. "
				"Add a [zookeeper] section to the configuration if this service should discover cluster instances.",
				struct_data={},
			)

		# Initialize API service
		self.ASABApiService = asab.api.ApiService(self)
		self.ASABApiService.initialize_web(self.WebContainer)
		self.ASABApiService.initialize_zookeeper(self.ZooKeeperContainer)

		# Initialize authorization
		self.AuthService = asab.web.auth.AuthService(self)

		# Get the discovery service
		self.DiscoveryService = self.get_service("asab.DiscoveryService")

		# Initialize handlers
		self.ProxyWebHandler = ProxyWebHandler(self, self.DiscoveryService)

		L.log(
			asab.LOG_NOTICE,
			"ASAB Discovery application initialized and ready to accept proxy requests.",
			struct_data={
				"web_listen": asab.Config.get("web", "listen", fallback=""),
				"zookeeper_enabled": self.ZooKeeperContainer is not None,
			},
		)
