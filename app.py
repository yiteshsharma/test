import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen


def load_environment() -> None:
	env_file = Path(__file__).with_name(".env")
	if not env_file.is_file():
		return

	for line in env_file.read_text(encoding="utf-8").splitlines():
		entry = line.strip()
		if not entry or entry.startswith("#"):
			continue

		name, separator, value = entry.partition("=")
		if not separator or not name.strip():
			raise ValueError(f"Invalid .env entry: {entry}")
		os.environ.setdefault(name.strip(), value.strip())


load_environment()

PORT = int(os.environ["PORT"])
GITHUB_API_TIMEOUT_SECONDS = float(os.environ["GITHUB_API_TIMEOUT_SECONDS"])
LOG_LEVEL = os.environ["LOG_LEVEL"].upper()

logging.basicConfig(
	level=LOG_LEVEL,
	format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("gists-api")


class GistHandler(BaseHTTPRequestHandler):
	def _send_json(self, status_code: int, payload: object) -> None:
		body = json.dumps(payload).encode("utf-8")
		self.send_response(status_code)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def do_GET(self) -> None:
		path = urlsplit(self.path).path.strip("/")
		logger.debug("Received request for %s", path)
		if path == "health":
			self._send_json(200, {"status": "ok"})
			return

		username = path
		if not username or "/" in username:
			self._send_json(404, {"error": "Expected a GitHub username in the path"})
			return

		url = f"https://api.github.com/users/{quote(username, safe='')}/gists"
		try:
			logger.info("Fetching public Gists for %s", username)
			with urlopen(url, timeout=GITHUB_API_TIMEOUT_SECONDS) as response:
				gists = json.load(response)
		except HTTPError as error:
			status_code = error.code
			logger.warning("GitHub returned HTTP %s for %s", status_code, username)
			error.close()
			self._send_json(status_code, {"error": "GitHub API request failed"})
			return
		except TimeoutError:
			logger.warning("GitHub request timed out for %s", username)
			self._send_json(502, {"error": "GitHub API request timed out"})
			return
		except URLError as error:
			logger.warning("GitHub request failed for %s: %s", username, error.reason)
			self._send_json(502, {"error": "GitHub API is unavailable"})
			return
		except json.JSONDecodeError:
			logger.error("GitHub returned invalid JSON for %s", username)
			self._send_json(502, {"error": "GitHub returned invalid JSON"})
			return

		self._send_json(200, gists)


def main() -> None:
	logger.info("Starting Gists API on port %s", PORT)
	ThreadingHTTPServer(("0.0.0.0", PORT), GistHandler).serve_forever()


if __name__ == "__main__":
	main()
