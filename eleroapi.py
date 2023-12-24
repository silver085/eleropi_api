import socket
import requests
import logging

LOGGER = logging.getLogger(__name__)


class NoDeviceAvailable(BaseException):
    pass


class UrlConstants:
    URL_PING = "/device/ping"
    URL_LOGIN = "/users/token"
    URL_GETBLINDS = "/blinds/getblinds"
    TOGGLE_DISCOVERY = "/blinds/indiscovery"


class EleroRequestError(BaseException):
    pass


class EleroApiError(ConnectionError):
    pass


class EleroAPI:
    username: str
    password: str
    host: str
    baseUrl: str
    isAuthenticated: bool
    token: str

    def __init__(self, username: str, password: str, host: str = None, autodiscovery: bool = True,
                 isLocal: bool = False):
        self.username = username
        self.password = password
        if autodiscovery:
            try:
                self.host = self._device_available()
            except RuntimeError:
                raise NoDeviceAvailable("Can't find any device over the network")
        else:
            self.host = host
        if not isLocal:
            self.baseUrl = f"http://{self.host}:8000"
        else:
            self.baseUrl = f"http://localhost:8000"

        self.session = requests.Session()
        self.isAuthenticated = False
        self.device_id = None
        self._ping()
        self._login()

    def get_blinds(self):
        url = f"{self.baseUrl}{UrlConstants.URL_GETBLINDS}"
        r = self._do_request(url=url, method="GET")
        return r["blinds"]

    def get_blind(self, blindId):
        url = f"{self.baseUrl}{UrlConstants.URL_GETBLINDS}/{blindId}"
        r = self._do_request(url=url, method="GET")
        return r["blind"]

    @staticmethod
    def _device_available():
        if socket.gethostbyname("raspberrypi.local") is not None: return "raspberrypi.local"
        if socket.gethostbyname("eleropi.local") is not None: return "eleropi.local"
        return None

    def _login(self):
        url = f"{self.baseUrl}{UrlConstants.URL_LOGIN}"
        data = {
            "username": self.username,
            "password": self.password
        }
        r = self._do_request(url=url, method="POST", data=data, is_json=False)
        LOGGER.debug(f"Got login response: {r}")
        self.isAuthenticated = True
        self.token = r["access_token"]

    def _ping(self):
        url = f"{self.baseUrl}{UrlConstants.URL_PING}"
        r = self._do_request(url=url, method="GET")
        LOGGER.debug(f"Got ping response: {r}")
        self.device_id = r["device_unique_id"]

    def start_discovery(self):
        url = f"{self.baseUrl}{UrlConstants.TOGGLE_DISCOVERY}"
        r = self._do_request(url=url, method="GET")
        if r["discovery_active"]: return
        r = self._do_request(url=url, method="PUT")
        if not r["discovery_active"]: raise EleroRequestError("Cannot put device in discovery")

    def stop_discovery(self):
        url = f"{self.baseUrl}{UrlConstants.TOGGLE_DISCOVERY}"
        r = self._do_request(url=url, method="GET")
        if not r["discovery_active"]: return
        r = self._do_request(url=url, method="PUT")
        if r["discovery_active"]: raise EleroRequestError("Failed putting device in stop discovery")

    def _do_request(self, url, method, data=None, is_json: bool = True):
        headers = {}
        if self.isAuthenticated:
            headers.update({"WWW-Authenticate": self.token})
        try:
            if is_json:
                response = self.session.request(url=url, method=method, json=data, headers=headers)
            else:
                response = self.session.request(url=url, method=method, data=data, headers=headers)

            if response.status_code != 200:
                raise EleroRequestError(f"Response: {response.json()}")
            else:
                return response.json()
        except ConnectionError:
            LOGGER.error(f"Connection to {url} failed. Is eleropi running over network?")
            raise EleroApiError(f"Cannot connect to: {url}")


class EleroClient:
    api: EleroAPI
    device_id: str
    blinds: None

    def __init__(self, username: str, password: str):
        self.api = EleroAPI(username=username, password=password, isLocal=True)
        self.device_id = self.api.device_id
        self.update()

    def update(self):
        self.blinds = self.api.get_blinds()

    def start_discovery(self):
        self.api.start_discovery()

    def stop_discovery(self):
        self.api.stop_discovery()

    def get_blind(self, blind_id):
        return self.api.get_blind(blindId=blind_id)


client = EleroClient("ha_user@local.dns", "ha_user")
client.start_discovery()
client.stop_discovery()
print(f"Device id {client.device_id}")
print(f"Blinds: {client.blinds}")
first_blind = client.blinds[0]
b_id0 = first_blind["blind_id"]
print(f"Blind update {b_id0}: {client.get_blind(blind_id=b_id0)}")
