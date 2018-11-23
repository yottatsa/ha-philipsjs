import logging

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

try:
    from typing import Optional, Union, Any, List, Dict, Tuple  # noqa
except ImportError:
    pass

logger = logging.getLogger(__name__)
BASE_URL = "http://{0}:1925/{1}/{2}"
NEW_BASE_URL = "https://{0}:1926/{1}/{2}"
TIMEOUT = 5.0
CHANNELS_TIMEOUT = 60.0
DEFAULT_API_VERSION = 1

AMBILIGHT_STYLES = {
	("FOLLOW_VIDEO", "MANUAL_HUE"): "Manual",
	("FOLLOW_VIDEO", "STANDARD"): "Standard",
	("FOLLOW_VIDEO", "NATURAL"): "Natural",
	("FOLLOW_VIDEO", "IMMERSIVE"): "Football",
	("FOLLOW_VIDEO", "VIVID"): "Vivid",
	("FOLLOW_VIDEO", "GAME"): "Game",
	("FOLLOW_VIDEO", "COMFORT"): "Comfort",
	("FOLLOW_VIDEO", "RELAX"): "Relax",
	("FOLLOW_AUDIO", "ENERGY_ADAPTIVE_BRIGHTNESS"): "Lumina",
	("FOLLOW_AUDIO", "ENERGY_ADAPTIVE_COLORS"): "Colora",
	("FOLLOW_AUDIO", "UV_METER"): "Retro",
	("FOLLOW_AUDIO", "SPECTUM_ANALYSER"): "Spectrum",
	("FOLLOW_AUDIO", "KNIGHT_RIDER_ALTERNATING"): "Scanner",
	("FOLLOW_AUDIO", "RANDOM_PIXEL_FLASH"): "Rhythm",
	("FOLLOW_AUDIO", "MODE_RANDOM"): "Party",
	("FOLLOW_COLOR", "HOT_LAVA"): "Hot Lava",
}


class PhilipsTV(object):
    def __init__(self, host, api_version=None, user=None, password=None):
        # type: (str, Union[int, str, None]) -> None
        self._host = host  # type: str
        self._user = user
        self._password = password
        self._session = requests.Session()
        retry = Retry(connect=1, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1)
        self._session.mount(self._user and 'https://' or 'http://', adapter)
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
        self.sources = {}
        self._sources = {}  # type: Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, str]]]]
        self.source_id = None
        self.channels = None  # type: Optional[Dict[str, Dict[str, str]]]
        self.channel_id = None
        self.ambilight = {}
        self.ambilight_supportedstyles = {}
        self.getSystem()

    def _formatUrl(self, path):
        if self._user:
            return NEW_BASE_URL.format(self._host, self.api_version, path)
        else:
            return BASE_URL.format(self._host, self.api_version, path)

    def _getReq(self, path, timeout=TIMEOUT):
        # type: (str, float) -> Optional[Dict[str, Any]]
        try:
            if not self.on:
                return None
            resp = self._session.get(
                self._formatUrl(path),
                timeout=timeout
            )
            self.on = True
            if resp.status_code != 200:
                return None
            return resp.json()
        except requests.exceptions.RequestException:
            self.on = False
            return None

    def _postReq(self, path, data):
        try:
            if not self.on:
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
        except requests.exceptions.RequestException:
            logger.debug('post error', exc_info=True)
            self.on = False
            return False

    def update(self, sources=False):
        # type: (bool) -> None
        self.getSystem()
        self.getName()
        self.getAudiodata()

        self.getSourceId()
        self.getChannelId()

        if sources or (
            self.source_id and self._sources and self.source_id not in self._sources
        ) or not self._sources:
            self.getSources()
            self.getChannels()
        
    def getName(self):  # type: (...) -> None
        if self.system and "name" in self.system:
            self.name = self.system["name"]
        else:
            r = self._getReq("system/name")
            if r:
                self.name = r["name"]

    def getSystem(self):  # type: (...) -> None
        self.on = True
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
        if self.api_version < 5:
            r = self._getReq("channels", timeout=CHANNELS_TIMEOUT)
            if r:
                self.channels = r

    def getChannelId(self):
        if self.api_version < 5:
            r = self._getReq("channels/current")
            if r:
                self.channel_id = r["id"]

    def setChannel(self, id):
        if self.api_version >= 5:
            return self.setSource(id)
        if self._postReq("channels/current", {"id": id}):
            self.channel_id = id

    def getChannelLists(self):
        # type: (...) -> List[Tuple[str, Dict[str, Any]]]
        if self.api_version >= 5:
            r = self._getReq("channeldb/tv", timeout=CHANNELS_TIMEOUT)
            if r:
                # could be alltv and allsat
                return [
                    (n, i)
                    for n, l in r.items()
                    for i in l
                ]
            else:
                return []
        else:
            return [("channelLists", {"id": "alltv", "name": "TV channels", "listType": "TV"})]

    def getSources(self):  # type: (...) -> None
        if self.api_version >= 5:
            self._sources = {}
            self._sources_lists = {}
            for listType, channelList in self.getChannelLists():
                listId = channelList["id"]
                r = self._getReq("channeldb/tv/{}/{}".format(listType, listId), timeout=CHANNELS_TIMEOUT)
                if r:
                    self._sources_lists.setdefault(listType, [])
                    for sourceItem in r.get("channels") or r.get("Channel") or []:
                        ccid = sourceItem["ccid"]
                        self._sources_lists[listType].append(ccid)
                        source = self._sources.setdefault(ccid, {})
                        source.update(sourceItem)
                        source['channelList'] = channelList
                        name = source.get("name")
                        if not name or not name.strip("-"):
                            name = str(source["preset"])
                        source["prettyName"] = "{} - {}".format(channelList["listType"], name)
            logger.debug(str(self._sources_lists))
            self.sources = sorted(self._sources_lists.values(), key=len)[0]
        else:
            r = self._getReq("sources")
            if r:
                self._sources = r
            self.sources = sorted(self._sources.keys())


    def getSourceId(self):
        if self.api_version >= 5:
            r = self._getReq("activities/tv")
            if r and r["channel"]:
                # it could be empty if HDMI is set
                self.source_id = r["channel"]["ccid"]
            else:
                self.source_id = None
        else:
            r = self._getReq("sources/current")
            if r:
                self.source_id = r["id"]
            else:
                self.source_id = None

    def getSourceName(self, srcid):  # type: (str) -> Optional[str]
        source = self._sources.get(srcid)
        if source:
            if self.api_version >= 5:
                return source.get("prettyName")
            else:
                return source.get("name")

    def setSource(self, srcid):
        if self.api_version >= 5:
            source = self._sources.get(srcid)
            if self._postReq(
                "activities/tv",
                {
                    "channelList": {"id": source["channelList"]["id"]},
                    "channel": {"ccid": srcid}
                }
            ):
                self.source_id = srcid
        else:
            if self._postReq("sources/current", {"id": ercid}):
                self.source_id = srcid

    def setVolume(self, level):
        if level:
            if self.min_volume != 0 or not self.max_volume:
                self.getAudiodata()
            if not self.on:
                return
            try:
                targetlevel = int(level * self.max_volume)
            except ValueError:
                logger.warning("Invalid audio level %s" % str(level))
                return
            if targetlevel < self.min_volume + 1 or targetlevel > self.max_volume:
                logger.warning(
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

    def getAmbilightStyles(self):
        self.ambilight_supportedstyles = AMBILIGHT_STYLES.copy()
        r = self._getReq("ambilight/supportedstyles")
        if not r:
            return
        styles = r.get("supportedStyles", [])
        for style in styles:
            for alg in style.get("algorithms", [None]):
                self.ambilight_supportedstyles.setdefault(
                    (style["styleName"], alg),
                    (alg and alg.title() or style["styleName"])
                )

    def getAmbilight(self):
        self.getSystem()
        conf = self._getReq("ambilight/currentconfiguration")
        if conf:
            self.ambilight = conf
            if not self.ambilight_supportedstyles:
                self.getAmbilightStyles()
            if "styleName" in conf and "menuSetting" in conf:
                self.ambilight_supportedstyles.setdefault(
                    (conf["styleName"], conf["menuSetting"]),
                    conf["menuSetting"].title(),
                )

    def setAmbilight(self, styleName, menuSetting=None, algorithm=None, isExpert=False, **kwargs):
        body = {
            "styleName": styleName,
            "isExpert": isExpert,
        }
        if menuSetting:
            body["menuSetting"] = menuSetting
        if algorithm:
            body["algorithm"] = algorithm
        body.update(kwargs)
        print(body)
        return self._postReq("ambilight/currentconfiguration", body)

    def setAmbilightStyle(self, style):
        settings = {v: k for k, v in self.ambilight_supportedstyles.items()}.get(style)
        if settings:
            return self.setAmbilight(*settings)

    def setAmbilightColor(self, hue, saturation, brightness, speed=255):
        return self.setAmbilight(
            "FOLLOW_COLOR",
            algorithm="MANUAL_HUE",
            isExpert=True,
            colorSettings={
                "color": {
                    "hue": int(hue*(255/360)),
                    "saturation": int(saturation*(255/100)),
                    "brightness": brightness,
                },
                "colorDelta": {"hue":0, "saturation":0, "brightness":0},
                "speed": speed,
            }
        )

    def setAmbilightPower(self, on):
        if self.ambilight:
            self._postReq("ambilight/power", {"power": on and "On" or "Off"})
            self.ambilight["power_on"] = on
