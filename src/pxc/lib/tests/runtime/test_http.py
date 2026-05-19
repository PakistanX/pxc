import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

from .utils import create_manifest, make_activity_runtime


class TestHttpRequest:
    """Tests for httpRequest host function."""

    def test_error_when_no_http_capability(self, tmp_path: Path) -> None:
        """Should return status=0 when no HTTP capability declared."""
        manifest = create_manifest(capabilities={})
        ctx = make_activity_runtime(tmp_path, manifest)

        result = ctx.http_request("https://example.com", "GET", "", [])

        data = json.loads(result)
        assert data["status"] == 0
        assert data["headers"] == []
        assert (
            "HTTP requests to example.com not allowed. Allowed hosts: []"
            in data["body"]
        )

    def test_error_when_host_not_allowed(self, tmp_path: Path) -> None:
        """Should return status=0 when host not in allowed list."""
        manifest = create_manifest(
            capabilities={"http": {"allowed_hosts": ["api.example.com"]}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        result = ctx.http_request("https://evil.com/hack", "GET", "", [])

        data = json.loads(result)
        assert data["status"] == 0
        assert "not allowed" in data["body"]

    @patch("pxc.lib.runtime.urllib.request.urlopen")
    def test_success_when_allowed(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        """Should return structured response with status, headers, body."""
        manifest = create_manifest(
            capabilities={"http": {"allowed_hosts": ["api.example.com"]}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": "test"}'
        mock_response.status = 200
        mock_response.getheaders.return_value = [
            ("Content-Type", "application/json"),
        ]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = ctx.http_request(
            "https://api.example.com/data",
            "POST",
            "body",
            [("Content-Type", "application/json")],
        )

        data = json.loads(result)
        assert data["status"] == 200
        assert data["body"] == '{"data": "test"}'
        assert ["Content-Type", "application/json"] in data["headers"]
        mock_urlopen.assert_called_once()

    @patch("pxc.lib.runtime.urllib.request.urlopen")
    def test_handles_http_error(self, mock_urlopen: MagicMock, tmp_path: Path) -> None:
        """Should return structured response on HTTPError."""
        manifest = create_manifest(
            capabilities={"http": {"allowed_hosts": ["example.com"]}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        error = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None  # type: ignore[arg-type]
        )
        error.read = MagicMock(return_value=b"not found")  # type: ignore[method-assign]
        mock_urlopen.side_effect = error

        result = ctx.http_request("https://example.com", "GET", "", [])

        data = json.loads(result)
        assert data["status"] == 404
        assert data["body"] == "not found"

    @patch("pxc.lib.runtime.urllib.request.urlopen")
    def test_handles_url_error(self, mock_urlopen: MagicMock, tmp_path: Path) -> None:
        """Should return status=0 on URLError."""
        manifest = create_manifest(
            capabilities={"http": {"allowed_hosts": ["example.com"]}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = ctx.http_request("https://example.com", "GET", "", [])

        data = json.loads(result)
        assert data["status"] == 0
        assert "Connection refused" in data["body"]
