# -*- coding: UTF-8 -*-
# Research It - small HTTP helper built on urllib (no third-party modules).

import socket
import ssl
import urllib.error
import urllib.request

from .parsing import ResearchError

USER_AGENT = "NVDA-QuickResearch/1.0 (NVDA add-on; https://github.com/rajathtirumangalam/Quickresearch)"
MAX_BYTES = 1500000


def fetch(url, timeout=10):
	"""GET a web address and return the body bytes. Raises ResearchError on failure."""
	if not url.lower().startswith(("http://", "https://")):
		raise ResearchError("badresponse")
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			return response.read(MAX_BYTES)
	except urllib.error.HTTPError as error:
		if error.code in (400, 404, 422):
			raise ResearchError("nothing")
		raise ResearchError("network")
	except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError, OSError):
		raise ResearchError("network")
