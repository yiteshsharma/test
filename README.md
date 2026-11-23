# GitHub Public Gists API

`GET /<username>` fetches that GitHub user's public Gists and returns them as
JSON. `.env` sets the API port to `8080`. No third-party Python
packages or GitHub token are required.

## Configuration and logs

The app loads these values from `.env` automatically when run locally. Docker
receives the same values through `--env-file`.

- `PORT`: listening port (`8080`).
- `GITHUB_API_TIMEOUT_SECONDS`: GitHub request timeout in seconds (`10`).
- `LOG_LEVEL`: application log level (`INFO`).

Startup and GitHub errors are logged. Docker captures logs for `docker logs`.

## Request flow

```mermaid
flowchart TD
	request["GET /<username>"] --> valid{"One username segment?"}
	valid -- No --> invalid["404 JSON<br/>Invalid path"]
	valid -- Yes --> fetch["Fetch public Gists<br/>GitHub API"]
	fetch --> result{"GitHub response?"}
	result -- Success --> success["200 JSON<br/>Gists list or []"]
	result -- HTTP error --> http_error["Forward HTTP status<br/>JSON error"]
	result -- Network, timeout, invalid JSON --> unavailable["502 JSON<br/>GitHub unavailable"]

	classDef request fill:#e8f4ec,stroke:#3d9b64,color:#1f2328
	classDef decision fill:#fff7e6,stroke:#d69e2e,color:#1f2328
	classDef success fill:#e8f4ec,stroke:#3d9b64,color:#1f2328
	classDef error fill:#fff1f0,stroke:#cf4b4b,color:#1f2328
	class request,fetch request
	class valid,result decision
	class success success
	class invalid,http_error,unavailable error
```

## Run locally

Requires Python 3.10 or later.

The app loads `.env` automatically when you start it:

```sh
python3 app.py
```

In a second terminal, request a user's Gists:

```sh
curl http://localhost:8080/octocat
```

Check that the API process is responsive without calling GitHub:

```sh
curl http://localhost:8080/health
```

## Run tests

Run the full suite:

```sh
python3 -m unittest discover -s tests -v
```

The tests mock GitHub and do not require network access.

Run one test case:

```sh
PYTHONPATH=tests python3 -m unittest test_app.GistAPITest.test_returns_users_gists -v
```

Replace the final method name to run a different test.

## Run with Docker

```sh
docker build -t public-gists-api .
docker run --rm --env-file .env -p 8080:8080 public-gists-api
```

Docker periodically checks `/health` and reports the container status. If you
change settings in `.env`, Docker passes them into the container.