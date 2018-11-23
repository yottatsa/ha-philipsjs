#!/usr/bin/python3

import sys
import logging
import json
from typing import Any, Dict, List

from haphilipsjs import PhilipsTV

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
            if dev in ('philips_tv', 'DLNA'):
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
            tv._session = None
            logger.info("State: %s", json.dumps(tv.__dict__))
        except Exception as e:
            logger.exception("Failed")


if __name__ == '__main__':
    main(sys.argv[1:])
