#!/usr/bin/python3

import sys
import logging
import json
from typing import Any, Dict, List

from haphilipsjs import PhilipsTV, AMBILIGHT_STYLES

logger = logging.getLogger(__name__)


class DebugPhilipsTV(PhilipsTV):
    def __init__(self, *args, **kwargs) -> None:
        self.requests = {}  # type: Dict[str, Any]
        super().__init__(*args, **kwargs)

    def _getReq(self, path: str, *args, **kwargs) -> Any:
        result = super()._getReq(path, *args, **kwargs)  # type: Any
        self.requests[path] = result
        return result


def discover() -> List[str]:
    try:
        from netdisco.discovery import NetworkDiscovery
        netdis = NetworkDiscovery()
        netdis.scan()
        results = []  # type: List[str]
        for dev in netdis.discover():
            if dev in ('dlna_dmr'):
                info = netdis.get_info(dev)
                logger.info("Discovered %s %s", dev, info)
                results.extend([dev['host'] for dev in info])
        netdis.stop()
        return results
    except ImportError:
        return []


def main(devices: List[str]) -> None:
    logging.basicConfig(level=logging.DEBUG)
    if not devices:
        devices = discover()
    for dev in devices:
        try:
            tv = DebugPhilipsTV(dev)
            tv.update()
            tv.update()
            tv.getAmbilight()
            logger.info("Sources: %s", [tv.getSourceName(s) for s in tv.sources])
            logger.info("Current Source: %s", tv.getSourceName(tv.source_id))
            logger.info("Ambilight: %s", tv.ambilight)
            logger.info(
                "Supported Ambilight Styles: %s",
                tv.ambilight_supportedstyles.keys() - AMBILIGHT_STYLES.keys()
            )
            logger.debug("Requests: %s", json.dumps(tv.requests))
        except Exception:
            logger.exception("Failed")


if __name__ == '__main__':
    main(sys.argv[1:])
