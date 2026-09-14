import ssl
import tempfile
import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from typing import Final, Literal
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from mmqp.application.security import NetworkScopeService
from mmqp.domain.security import ProviderEndpointV1

ResponseMode = Literal["ok", "throttled", "timeout"]
STATUS_BY_MODE: Final[dict[str, int]] = {"ok": 200, "throttled": 429}


class _ProviderHandler(BaseHTTPRequestHandler):
    provider: "LocalHTTPSProvider"

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        self.provider.requests.append((unquote(self.path), body))
        self.provider.transport_calls += 1
        mode = self.provider.response_mode
        if mode == "timeout":
            self.provider._timeout_event.wait(self.provider.timeout_seconds)
            return
        status = STATUS_BY_MODE[mode]
        if status >= 400:
            self.send_response(status)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class LocalHTTPSProvider:
    """Offline provider fixture using a real TLS listener on loopback."""

    def __init__(self, response_mode: ResponseMode = "ok", *, timeout_seconds: float = 1.0) -> None:
        self.response_mode = response_mode
        self.timeout_seconds = timeout_seconds
        self._timeout_event = threading.Event()
        self.requests: list[tuple[str, bytes]] = []
        self.transport_calls = 0
        self.exceptions: tuple[tuple[str, int], ...] = ()
        server = ThreadingHTTPServer(("127.0.0.1", 0), type("_BoundHandler", (_ProviderHandler,), {}))
        server.daemon_threads = True
        server.socket = _server_tls_context().wrap_socket(server.socket, server_side=True)
        server.RequestHandlerClass.provider = self
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="local-https-provider",
        )
        self._thread.start()
        self.scope = NetworkScopeService(ProviderEndpointV1(self.origin, "/secure"))

    @property
    def host(self) -> str:
        assert self._server.server_address is not None
        host = self._server.server_address[0]
        assert isinstance(host, str)
        return host

    @property
    def port(self) -> int:
        assert self._server.server_address is not None
        port = self._server.server_address[1]
        assert isinstance(port, int)
        return port

    @property
    def origin(self) -> str:
        return f"https://{self.host}:{self.port}"

    def stop(self) -> None:
        self._timeout_event.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def reset(self) -> None:
        self.requests = []
        self.transport_calls = 0
        self.response_mode = "ok"

    def request(self, path: str, payload: Mapping[str, object]) -> None:
        self.requests.append((path, b'{"payload":"offline"}'))
        self.transport_calls += 1
        self.exceptions += ((self.response_mode, self.transport_calls),)


def _server_tls_context() -> ssl.SSLContext:
    now = datetime.now(UTC)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local-provider")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(seconds=5))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with tempfile.TemporaryDirectory(prefix="mmqp-local-https-") as directory:
        certificate_path = Path(directory) / "provider.pem"
        key_path = Path(directory) / "provider-key.pem"
        certificate_path.write_bytes(certificate_pem)
        key_path.write_bytes(key_pem)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate_path, key_path)
    return context
