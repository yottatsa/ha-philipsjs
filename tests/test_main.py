import unittest

from haphilipsjs.__main__ import main
import requests_mock
from .utils import HOST, get_response


class MainTestCase(unittest.TestCase):
    def test_main(self):
        V = 6
        with requests_mock.Mocker() as m:
            get_response(m.get, V, "system", "1/system")
            for url in ["system", "audio/volume", "channeldb/tv", "activities/tv"]:
                get_response(m.get, V, url)
            main([HOST])
