import logging

import requests

try:
    from typing import Optional, Union, Any, List, Dict, Tuple  # noqa
except ImportError:
    pass

LOG = logging.getLogger(__name__)
BASE_URL = "http://{0}:1925/{1}/{2}"
NEW_BASE_URL = "https://{0}:1926/{1}/{2}"
TIMEOUT = 5.0
CHANNELS_TIMEOUT = 30.0
CONNFAILCOUNT = 5
DEFAULT_API_VERSION = 1


class PhilipsTV(object):
    def __init__(self, host, api_version=None, user=None, password=None):
        # type: (str, Union[int, str, None]) -> None
        self._host = host  # type: str
        self._user = user
        self._password = password
        self._connfail = 0
        self._session = requests.Session()
        if self._user:
            self._session.mount('https://', HTTPAdapter(pool_connections=1))
        if api_version:
            self.api_version = int(api_version)  # type: int
        else:
            self.api_version = DEFAULT_API_VERSION  # type: int
        self.on = None  # type: Optional[bool]
        self.name = None  # type: Optional[str]
        self.system = None  # type: Optional[Dict[str, Any]]
        self.min_volume = None  # type: Optional[int]
        self.max_volume = None  # type: Optional[int]
        self.volume = None  # type: Optional[float]
        self.muted = None  # type: Optional[bool]
        self.sources = (
            None
        )  # type: Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, str]]]]
        self.source_id = None
        self.channels = None  # type: Optional[Dict[str, Dict[str, str]]]
        self.channel_id = None
        self.ambilight = None
        self.ignoreList = []
        self.getSystem()

    def _formatUrl(self, path):
        if self._user:
            return NEW_BASE_URL.format(self._host, self.api_version, path)
        else:
            return BASE_URL.format(self._host, self.api_version, path)

    def _getReq(self, path, timeout=TIMEOUT):
        # type: (str, float) -> Optional[Dict[str, Any]]
        try:
            if self._connfail:
                LOG.debug("Connfail: %i", self._connfail)
                self._connfail -= 1
                return None
            resp = self._session.get(
                self._formatUrl(path),
                timeout=timeout
            )
            if resp.status_code != 200:
                return None
            self.on = True
            return resp.json()
        except requests.exceptions.RequestException as err:
            LOG.debug("Exception: %s", str(err))
            self._connfail = CONNFAILCOUNT
            self.on = False
            return None

    def _postReq(self, path, data):
        try:
            if self._connfail:
                LOG.debug("Connfail: %i", self._connfail)
                self._connfail -= 1
                return False
            resp = self._session.post(
                self._formatUrl(path),
                json=data,
                timeout=TIMEOUT,
            )
            self.on = True
            if resp.status_code == 200:
                return True
            else:
                return False
        except requests.exceptions.RequestException as err:
            LOG.debug("Exception: %s", str(err))
            self._connfail = CONNFAILCOUNT
            self.on = False
            return False

    def update(self, channels=True):
        # type: (bool) -> None
        self.getSystem()
        self.getName()
        self.getAudiodata()

        if channels:
            self.getChannels()
            if self.api_version < 5:
                self.getSources()
        
        self.getChannelId()
        if self.api_version < 5:
            self.getSourceId()

    def getName(self):  # type: (...) -> None
        if self.system and "name" in self.system:
            self.name = self.system["name"]
        else:
            r = self._getReq("system/name")
            if r:
                self.name = r["name"]

    def getSystem(self):  # type: (...) -> None
        r = self._getReq("system")
        if r:
            self.system = r
            self.api_version = int(
                r.get("api_version", {}).get("Major") or DEFAULT_API_VERSION
            )

    def getAudiodata(self):  # type: (...) -> None
        audiodata = self._getReq("audio/volume")  # Optional[Dict[str, Any]]
        if audiodata:
            self.min_volume = int(audiodata["min"])
            self.max_volume = int(audiodata["max"])
            self.volume = int(audiodata["current"]) / self.max_volume
            self.muted = bool(audiodata["muted"])
        else:
            self.min_volume = None
            self.max_volume = None
            self.volume = None
            self.muted = None

    def getChannels(self):  # type: (...) -> None
        if self.api_version >= 5:
            self.getSources()
        else:
            r = self._getReq("channels", timeout=CHANNELS_TIMEOUT)
            if r:
                self.channels = r

    def getChannelId(self):
        if self.api_version >= 5:
            self.getSourceId()
        else:
            r = self._getReq("channels/current")
            if r:
                self.channel_id = r["id"]

    def setChannel(self, id):
        if self.api_version >= 5:
            return self.setSource(id)
        if self._postReq("channels/current", {"id": id}):
            self.channel_id = id

    def getChannelLists(self):
        # type: (...) -> List[Tuple[str, str]]
        if self.api_version >= 6:
            r = self._getReq("channeldb/tv", timeout=CHANNELS_TIMEOUT)
            if r:
                # could be alltv and allsat
                return [
                    (n, i["id"])
                    for n, l in r.items()
                    for i in l
                ]
            else:
                return []
        else:
            return ["alltv"]

    def getSources(self):  # type: (...) -> None
        self.sources = []
        if self.api_version >= 5:
            for listType, listId in self.getChannelLists():
                if listId in self.ignoreList:
                    continue
                r = self._getReq("channeldb/tv/{}/{}".format(listType, listId), timeout=CHANNELS_TIMEOUT)
                if r:
                    self.sources.extend(r.get("Channel", []))
        else:
            r = self._getReq("sources")
            if r:
                self.sources = r

    def getSourceId(self):
        if self.api_version >= 5:
            r = self._getReq("activities/tv")
            if r and r["channel"]:
                # it could be empty if HDMI is set
                self._source_id = r["channel"]["ccid"]
            else:
                self.source_id = None
        else:
            r = self._getReq("sources/current")
            if r:
                self.source_id = r["id"]
            else:
                self.source_id = None

    def getSourceName(
        self, srcid  # type: Union[Dict[str, str], str]
    ):  # type: (...) -> str
        if self.api_version >= 5 and isinstance(srcid, dict):
            name = srcid["name"]
            if not name.strip("-"):
                return str(srcid["preset"])
            else:
                return name
        elif isinstance(self.sources, dict) and isinstance(srcid, str):
            return str(self.sources.get(srcid, {}).get("name"))
        else:
            raise ValueError()

    def setSource(self, id):
        def setChannelBody(ccid):
            return {"channelList": {"id": "alltv"}, "channel": {"ccid": ccid}}

        if self.api_version >= 5:
            if self._postReq("activities/tv", setChannelBody(id["ccid"])):
                self.source_id = id
        else:
            if self._postReq("sources/current", {"id": id}):
                self.source_id = id

    def setVolume(self, level):
        if level:
            if self.min_volume != 0 or not self.max_volume:
                self.getAudiodata()
            if not self.on:
                return
            try:
                targetlevel = int(level * self.max_volume)
            except ValueError:
                LOG.warning("Invalid audio level %s" % str(level))
                return
            if targetlevel < self.min_volume + 1 or targetlevel > self.max_volume:
                LOG.warning(
                    "Level not in range (%i - %i)"
                    % (self.min_volume + 1, self.max_volume)
                )
                return
            self._postReq("audio/volume", {"current": targetlevel, "muted": False})
            self.volume = targetlevel

    def sendKey(self, key):
        self._postReq("input/key", {"key": key})

    def openURL(self, url):
        if self.api_version >= 6:
            if self.system and "browser" in (
                self.system.get("featuring", {})
                .get("jsonfeatures", {})
                .get("activities", [])
            ):
                self._postReq("activities/browser", {"url": url})

    def getAmbilight(self):
        power = self._getReq("ambilight/power")
        conf = self._getReq("ambilight/currentconfiguration")
        if power and conf:
            self.ambilight = {
                "power": power["power"] == "On",
                "currentconfiguration": conf,
            }
        else:
            self.ambilight = {}

    def setAmbilightPower(self, state):
        if self.ambilight and self.ambilight["power"] != state:
            self._postReq("ambilight/power", {"power": state and "On" or "Off"})
            self.ambilight_power["power"] = state
