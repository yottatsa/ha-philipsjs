import os
import json

VERSIONS = {1: "jointSPACE", 5: "65pus8700_12", 6: "50pus6272_05"}

HOST = "192.168.1.2"


def get_response(mock, api_version, path, url=None):
    fn = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "api",
        VERSIONS[api_version],
        "{}.json".format(path),
    )
    if not url:
        url = os.path.join(str(api_version), path)
    with open(fn, "r") as f:
        response = json.load(f)
    return (
        mock("http://{}:1925/{}".format(HOST, url), text=json.dumps(response)),
        response,
    )
