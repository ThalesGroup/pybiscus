import argparse
import os
from pathlib import Path
from typing import Optional

from pybiscus.session.auth import is_loopback

BUNDLE_PATH = Path(".pybiscus-cache/tls/ca-bundle.pem")
CA_BUNDLE_ENV = "REQUESTS_CA_BUNDLE"


def add_tls_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tls-cert", default=None, metavar="FILE",
                        help="certificate of this machine (certificates/gen_component_cert.sh): serve HTTPS instead of HTTP")
    parser.add_argument("--tls-key", default=None, metavar="FILE", help="private key of --tls-cert")
    parser.add_argument("--tls-ca", default=None, metavar="FILE",
                        help="CA the other components' certificates are signed by (certificates/ca/ca.crt), "
                             "trusted by this component and the runs it launches")


def check_tls_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("--tls-cert and --tls-key go together")
    for option, path in (("--tls-cert", args.tls_cert), ("--tls-key", args.tls_key), ("--tls-ca", args.tls_ca)):
        if path and not Path(path).is_file():
            parser.error(f"{option}: no file {path}")


def ssl_context(args: argparse.Namespace) -> Optional[tuple]:
    return (args.tls_cert, args.tls_key) if args.tls_cert else None


def scheme(args: argparse.Namespace) -> str:
    return "https" if args.tls_cert else "http"


def trust_ca(ca_path: Optional[str], bundle_path: Path = BUNDLE_PATH) -> Optional[Path]:
    """makes requests, here and in the runs this process launches, trust ca_path besides the usual
    authorities; returns the bundle written"""
    if not ca_path:
        return None
    # REQUESTS_CA_BUNDLE replaces the authorities requests trusts: with the CA alone, every call to
    # another site (W&B, a dataset hub) would fail its certificate check
    base = os.environ.get(CA_BUNDLE_ENV)
    if not base or Path(base).resolve() == bundle_path.resolve():
        import certifi
        base = certifi.where()
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(Path(base).read_text() + "\n" + Path(ca_path).read_text())
    os.environ[CA_BUNDLE_ENV] = str(bundle_path.resolve())
    return bundle_path


def untrusted_hint(url: str) -> str:
    return (f"the certificate of {url} is not trusted: give the agent (or this process) the CA that signed it, "
            f"--tls-ca certificates/ca/ca.crt, or set {CA_BUNDLE_ENV}")


def plain_agent_warning(manager_url: Optional[str], agent_url: str, name: str) -> Optional[str]:
    from urllib.parse import urlsplit
    manager, agent = urlsplit(manager_url or ""), urlsplit(agent_url)
    # browsers let an HTTPS page show http://localhost, never another host in HTTP
    if manager.scheme != "https" or agent.scheme != "http" or is_loopback(agent.hostname or ""):
        return None
    return (f"the agent '{name}' is reached in HTTP ({agent_url}) by this manager in HTTPS: its traffic travels in "
            f"clear, and the browsers block its page inside this one (start it with --tls-cert / --tls-key)")


def plain_http_warning(component: str, host: str, args: argparse.Namespace) -> Optional[str]:
    # a warning and not a refusal: behind an HTTPS reverse proxy, the component itself serves HTTP
    if args.tls_cert or is_loopback(host):
        return None
    return (f"⚠️  {component} listening on {host} without TLS: tokens, configurations and logs travel in clear "
            f"(--tls-cert / --tls-key, or an HTTPS reverse proxy, a VPN or an SSH tunnel; docs/multi-machine.md)")
