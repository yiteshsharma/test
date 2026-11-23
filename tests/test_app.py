import io
import json
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import app


class GistAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), app.GistHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_health_endpoint_returns_ok_without_calling_github(self) -> None:
        with patch("app.urlopen") as github_request:
            with urlopen(
                f"http://127.0.0.1:{self.server.server_port}/health"
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/json")
                self.assertEqual(json.load(response), {"status": "ok"})

        github_request.assert_not_called()

    def test_returns_users_gists(self) -> None:
        gists = [{"id": "example-gist", "description": "A public gist"}]
        github_response = json.dumps(gists).encode("utf-8")

        with patch("app.urlopen", return_value=io.BytesIO(github_response)) as github_request:
            with urlopen(
                f"http://127.0.0.1:{self.server.server_port}/octocat"
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/json")
                self.assertEqual(json.load(response), gists)

        github_request.assert_called_once_with(
            "https://api.github.com/users/octocat/gists",
            timeout=app.GITHUB_API_TIMEOUT_SECONDS,
        )

    def test_returns_empty_list_when_user_has_no_gists(self) -> None:
        with patch("app.urlopen", return_value=io.BytesIO(b"[]")):
            with urlopen(
                f"http://127.0.0.1:{self.server.server_port}/octocat"
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/json")
                self.assertEqual(json.load(response), [])

    def test_returns_json_error_for_invalid_path(self) -> None:
        with self.assertRaises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{self.server.server_port}/")

        self.assertEqual(error.exception.code, 404)
        self.assertEqual(
            error.exception.headers.get_content_type(), "application/json"
        )
        self.assertEqual(
            json.load(error.exception),
            {"error": "Expected a GitHub username in the path"},
        )
        error.exception.close()

    def test_returns_404_when_github_user_does_not_exist(self) -> None:
        github_error = HTTPError(
            "https://api.github.com/users/unknown-user/gists",
            404,
            "Not Found",
            None,
            io.BytesIO(),
        )

        with patch("app.urlopen", side_effect=github_error):
            with self.assertRaises(HTTPError) as error:
                urlopen(
                    f"http://127.0.0.1:{self.server.server_port}/unknown-user"
                )

        self.assertEqual(error.exception.code, 404)
        self.assertEqual(
            error.exception.headers.get_content_type(), "application/json"
        )
        self.assertEqual(
            json.load(error.exception),
            {"error": "GitHub API request failed"},
        )
        error.exception.close()

    def test_returns_502_when_github_is_unreachable(self) -> None:
        with patch("app.urlopen", side_effect=URLError("connection failed")):
            with self.assertRaises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{self.server.server_port}/octocat")

        self.assertEqual(error.exception.code, 502)
        self.assertEqual(
            error.exception.headers.get_content_type(), "application/json"
        )
        self.assertEqual(
            json.load(error.exception),
            {"error": "GitHub API is unavailable"},
        )
        error.exception.close()

    def test_returns_502_when_github_request_times_out(self) -> None:
        with patch("app.urlopen", side_effect=TimeoutError("request timed out")):
            with self.assertRaises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{self.server.server_port}/octocat")

        self.assertEqual(error.exception.code, 502)
        self.assertEqual(
            error.exception.headers.get_content_type(), "application/json"
        )
        self.assertEqual(
            json.load(error.exception),
            {"error": "GitHub API request timed out"},
        )
        error.exception.close()

    def test_returns_502_when_github_returns_invalid_json(self) -> None:
        with patch("app.urlopen", return_value=io.BytesIO(b"not-json")):
            with self.assertRaises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{self.server.server_port}/octocat")

        self.assertEqual(error.exception.code, 502)
        self.assertEqual(
            error.exception.headers.get_content_type(), "application/json"
        )
        self.assertEqual(
            json.load(error.exception),
            {"error": "GitHub returned invalid JSON"},
        )
        error.exception.close()


if __name__ == "__main__":
    unittest.main()