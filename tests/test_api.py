import unittest

from haphilipsjs import PhilipsTV
import requests_mock
from .utils import HOST, get_response


class ApiTestCase(unittest.TestCase):
    def test_test(self):
        pass

    def test_api_versions(self):
        for api_version in [1, 5, 6]:
            with requests_mock.Mocker() as m:
                api = m.get(
                    "http://{}:1925/{}/system".format(HOST, api_version), text="{}"
                )
                PhilipsTV(HOST, api_version)
                self.assertEquals(api.call_count, 1)

    def test_api_v1_detection(self):
        return self._test_api_version_detection(1)

    def test_api_v5_detection(self):
        return self._test_api_version_detection(5)

    def test_api_v6_detection(self):
        return self._test_api_version_detection(6)

    def _test_api_version_detection(self, api_version):
        with requests_mock.Mocker() as m:
            if api_version > 1:
                detection, _ = get_response(m.get, api_version, "system", "1/system")
            api, response = get_response(m.get, api_version, "system")
            tv = PhilipsTV(HOST)
            tv.getSystem()
            tv.getName()

            if api_version > 1:
                self.assertEquals(detection.call_count, 1)
                self.assertEquals(api.call_count, 1)
            else:
                self.assertEquals(api.call_count, 2)

            self.assertEquals(tv.api_version, api_version)
            self.assertEquals(tv.name, response["name"])

    def test_v1(self):
        V = 1
        with requests_mock.Mocker() as m:
            for url in ["system", "audio/volume", "channels", "channels/current"]:
                get_response(m.get, V, url)
            _, sources = get_response(m.get, V, "sources")
            _, source_id = get_response(m.get, V, "sources/current")

            tv = PhilipsTV(HOST)
            tv.update()
            self.assertIsNotNone(tv.channels)
            self.assertIsNotNone(tv.sources)
            self.assertEqual(
                tv.getSourceName(tv.source_id), sources[source_id["id"]]["name"]
            )
            self.assertIsNotNone(tv.volume)

    def test_v6_empty_channels(self):
        V = 6
        with requests_mock.Mocker() as m:
            get_response(m.get, V, "system", "1/system")
            for url in ["system", "audio/volume", "channeldb/tv", "activities/tv"]:
                get_response(m.get, V, url)

            tv = PhilipsTV(HOST)
            tv.update()
            self.assertIsNone(tv.channels)
            self.assertEquals(tv.sources, [])
            self.assertIsNotNone(tv.volume)
