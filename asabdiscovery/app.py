import asab.api
import asab.web
import asab.web.rest
import asab.zookeeper
import asab.proactor
import asab.metrics

import asab.api.discovery

from .proxy.handler import ProxyWebHandler


asab.Config.add_defaults({
	"web": {
		"listen": "8897",  # Well-known port of asab discovery
	},
	"auth": {
		"public_keys_url": "http://seacat-auth.service_id.asab/.well-known/jwks.json"
	},
})


class ASABDiscoveryApplication(asab.Application):

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

		else:
			self.ZooKeeperContainer = None

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
