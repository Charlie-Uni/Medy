"""Small CI-only loopback HTTP probe, usable inside a network-isolated runtime container."""

import sys
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import urlopen


def status(url):
    try:
        with urlopen(url, timeout=3) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except (OSError, HTTPException):
        return None


if __name__ == "__main__":
    print(status(sys.argv[1]))
