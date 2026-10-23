import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# An invitation lets one lower-level manager (a site) report to an upper-level one under the bouquet
# the upper level chose, with a token of its own, until it expires or is revoked: the session token,
# shared by every participant, let anyone holding it report under any bouquet.

INVITATIONS_DIR = Path("invitations")
ISSUED_DIR = INVITATIONS_DIR / "issued"
RECEIVED_DIR = INVITATIONS_DIR / "received"
REGISTRY_DIR = Path(".pybiscus-cache/invitations")
INVITATION_ENV = "PYBISCUS_INVITATION"
REQUIRE_INVITATION_ENV = "PYBISCUS_REQUIRE_INVITATION"
DEFAULT_DAYS = 90
# the expiry is shown as close this many days before
SOON_DAYS = 14
# a bouquet names the issued file and the registry's entry: no separator, no "." or ".."
BOUQUET_NAME = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]+$")
CA_FILE_DEFAULT = Path("certificates/ca/ca.crt")


def valid_bouquet(name) -> bool:
    return isinstance(name, str) and bool(BOUQUET_NAME.match(name))


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _digest(token: str) -> str:
    # only the digest is kept: the registry read by someone else gives no token
    return hashlib.sha256(token.encode()).hexdigest()


class Invitation(BaseModel):
    """the file the upper level's operator hands to the site's"""
    model_config = ConfigDict(extra="forbid")

    upper_url: str = Field(description="the upper-level manager, in HTTPS")
    upper_bouquet: str = Field(description="the upper level's bouquet")
    bouquet: str = Field(description="the bouquet of the invited site, set by the upper level")
    token: str = Field(description="the site's own token, presented to the upper-level manager")
    expires: dt.datetime = Field(description="after this date, the upper level refuses the token")
    ca_certificate: str = Field(description="the CA the upper-level manager's certificate is signed by (PEM)")

    @field_validator("upper_url")
    @classmethod
    def _https(cls, url):
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError(f"an https:// URL expected: {url!r}")
        return url.rstrip("/")

    @field_validator("bouquet", "upper_bouquet")
    @classmethod
    def _bouquet(cls, name):
        if not valid_bouquet(name):
            raise ValueError(f"a bouquet in letters, digits, '.', '_' or '-' expected: {name!r}")
        return name

    @field_validator("expires")
    @classmethod
    def _aware(cls, when):
        return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)

    @field_validator("ca_certificate")
    @classmethod
    def _pem(cls, text):
        if "-----BEGIN CERTIFICATE-----" not in text:
            raise ValueError("a PEM certificate expected")
        return text


def issued_file_name(upper_bouquet: str, bouquet: str) -> str:
    # not an arrow: '>' is forbidden in Windows file names, '→' damaged by some tools
    return f"{upper_bouquet}_downto_{bouquet}.yml"


def _write_secret(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    path.chmod(0o600)


def readable_by_others(path: Path) -> bool:
    return os.name == "posix" and bool(path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def read_invitation(path) -> tuple[Invitation, list]:
    """the invitation and the warnings to show; ValueError when the file is not one"""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"{path}: {e}")
    try:
        invitation = Invitation.model_validate(data)
    except ValueError as e:
        raise ValueError(f"{path} is not a valid invitation: {e}")
    warnings = []
    if readable_by_others(path):
        warnings.append(f"{path} holds a token and is readable by other users: chmod 600 {path}")
    left = invitation.expires - _now()
    if left.total_seconds() <= 0:
        warnings.append(f"the invitation expired on {invitation.expires:%Y-%m-%d}: ask the upper level's operator for "
                        f"another one (unless it was extended)")
    elif left.days < SOON_DAYS:
        warnings.append(f"the invitation expires on {invitation.expires:%Y-%m-%d}")
    return invitation, warnings


def received_invitation() -> Optional[Path]:
    """the only file of invitations/received, None without; ValueError with several"""
    if not RECEIVED_DIR.is_dir():
        return None
    files = sorted(p for p in RECEIVED_DIR.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml"))
    if len(files) > 1:
        raise ValueError(f"{RECEIVED_DIR} holds several invitations ({', '.join(p.name for p in files)}): keep one")
    return files[0] if files else None


# ************************** the upper level's registry

def registry_path(port: int) -> Path:
    return REGISTRY_DIR / f"manager-{port}.json"


@contextmanager
def _locked(port: int):
    """the command line and the manager's page may issue at the same time"""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(REGISTRY_DIR / f"manager-{port}.lock", "a")
    try:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except ImportError:   # Windows: no concurrent writer expected there
            pass
        yield
    finally:
        lock.close()


def load_registry(port: int) -> dict:
    path = registry_path(port)
    if not path.is_file():
        return {"manager": {}, "invitations": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("manager", {})
    data.setdefault("invitations", {})
    return data


def _save_registry(port: int, data: dict) -> None:
    path = registry_path(port)
    tmp = path.with_suffix(".tmp")
    _write_secret(tmp, json.dumps(data, indent=1, sort_keys=True))
    os.replace(tmp, path)


def record_manager(port: int, url: str, bouquet: Optional[str], https: bool, ca: Optional[str]) -> None:
    """what the invitations of this manager say about it, kept for the command line, which may
    issue them while the manager is stopped"""
    with _locked(port):
        data = load_registry(port)
        data["manager"] = {"url": url, "bouquet": bouquet, "https": https, "ca": ca}
        _save_registry(port, data)


def issue(port: int, bouquet: str, days: int = DEFAULT_DAYS, url: Optional[str] = None,
          upper_bouquet: Optional[str] = None, ca: Optional[str] = None, out_dir: Path = ISSUED_DIR) -> tuple[Invitation, Path]:
    """a new invitation for the bouquet, replacing the one it had; the file written"""
    if not valid_bouquet(bouquet):
        raise ValueError(f"bouquet {bouquet!r}: letters, digits, '.', '_' or '-' only")
    if not isinstance(days, int) or days < 1:
        raise ValueError(f"a number of days of at least 1 expected: {days!r}")
    with _locked(port):
        data = load_registry(port)
        manager = data["manager"]
        if manager and not manager.get("https") and url is None:
            raise ValueError(f"the manager on port {port} serves HTTP: the token would travel in clear at each contact. "
                             f"Start it with --tls-cert / --tls-key")
        url = url or manager.get("url")
        if not url:
            raise ValueError(f"no manager started on port {port} from this directory: give its URL (--url)")
        upper_bouquet = upper_bouquet or manager.get("bouquet") or f"manager-{port}"
        ca_path = Path(ca or manager.get("ca") or CA_FILE_DEFAULT)
        if not ca_path.is_file():
            raise ValueError(f"no CA certificate {ca_path}: give the session's CA (--ca certificates/ca/ca.crt)")
        token = secrets.token_urlsafe(32)
        expires = (_now() + dt.timedelta(days=days)).replace(microsecond=0)
        invitation = Invitation(upper_url=url, upper_bouquet=upper_bouquet, bouquet=bouquet, token=token,
                                expires=expires, ca_certificate=ca_path.read_text(encoding="utf-8"))
        data["invitations"][bouquet] = {"digest": _digest(token), "expires": expires.isoformat(),
                                        "issued": _now().replace(microsecond=0).isoformat(), "revoked": None}
        _save_registry(port, data)
    path = out_dir / issued_file_name(upper_bouquet, bouquet)
    _write_secret(path, invitation_text(invitation))
    return invitation, path


def invitation_text(invitation: Invitation) -> str:
    head = (f"# Invitation of the site '{invitation.bouquet}' by '{invitation.upper_bouquet}' ({invitation.upper_url}),\n"
            f"# valid until {invitation.expires:%Y-%m-%d}. It holds a token: hand it to the site's operator only,\n"
            f"# who puts it in invitations/received/ (or gives it with --invitation). Never commit it.\n")
    return head + yaml.safe_dump(json.loads(invitation.model_dump_json()), sort_keys=False, width=200)


def revoke(port: int, bouquet: str) -> None:
    with _locked(port):
        data = load_registry(port)
        entry = data["invitations"].get(bouquet)
        if entry is None:
            raise ValueError(f"no invitation for {bouquet!r}")
        entry["revoked"] = _now().replace(microsecond=0).isoformat()
        _save_registry(port, data)


def forget(port: int, bouquet: str) -> None:
    with _locked(port):
        data = load_registry(port)
        data["invitations"].pop(bouquet, None)
        _save_registry(port, data)


def _expired(entry: dict) -> bool:
    return dt.datetime.fromisoformat(entry["expires"]) <= _now()


def active(entry: Optional[dict]) -> bool:
    return bool(entry) and not entry.get("revoked") and not _expired(entry)


def invited_bouquet(port: int, token: Optional[str]) -> Optional[str]:
    """the bouquet whose active invitation holds this token, None otherwise"""
    if not token:
        return None
    digest = _digest(token)
    for bouquet, entry in load_registry(port)["invitations"].items():
        if active(entry) and secrets.compare_digest(entry["digest"], digest):
            return bouquet
    return None


def invitation_problem(port: int, token: Optional[str]) -> Optional[str]:
    """why this token, an invitation's, is no longer accepted; None if it is not one"""
    if not token:
        return None
    digest = _digest(token)
    for bouquet, entry in load_registry(port)["invitations"].items():
        if secrets.compare_digest(entry["digest"], digest) and not active(entry):
            return (f"the invitation of {bouquet} was revoked" if entry.get("revoked")
                    else f"the invitation of {bouquet} expired on {entry['expires'][:10]}")
    return None


def has_active_invitation(port: int, bouquet: str) -> bool:
    return active(load_registry(port)["invitations"].get(bouquet))


class SiteState(str, enum.Enum):
    """a site of the upper level's page; the page reads the icons and texts from here"""
    INVITED = "invited"         # never came
    PRESENT = "present"
    MISSING = "missing"         # came, no longer reports
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNEXPECTED = "unexpected"   # came without an invitation, refused
    ADMITTED = "admitted"       # came with the session token, without --require-invitation


SITE_STATE_ICON = {SiteState.INVITED: "⏳", SiteState.PRESENT: "✓", SiteState.MISSING: "⚠",
                   SiteState.EXPIRED: "⌛", SiteState.REVOKED: "✗", SiteState.UNEXPECTED: "⛔",
                   SiteState.ADMITTED: "○"}
SITE_STATE_TEXT = {SiteState.INVITED: "invited, not come yet", SiteState.PRESENT: "present",
                   SiteState.MISSING: "came, no longer reports", SiteState.EXPIRED: "invitation expired",
                   SiteState.REVOKED: "invitation revoked", SiteState.UNEXPECTED: "came without invitation, refused",
                   SiteState.ADMITTED: "present with the session token, no invitation"}


def site_state_protocol() -> dict:
    return {state.value: {"icon": SITE_STATE_ICON[state], "text": SITE_STATE_TEXT[state]} for state in SiteState}


def sites(port: int, reports: dict, refused: dict) -> list:
    """the invited sites and the refused ones, as the page lists them. reports: bouquet ->
    {"stale", "invited"}; refused: bouquet -> {"time", "reason"}"""
    rows = []
    now = _now()
    for bouquet, entry in sorted(load_registry(port)["invitations"].items()):
        report = reports.get(bouquet)
        if entry.get("revoked"):
            state = SiteState.REVOKED
        elif _expired(entry):
            state = SiteState.EXPIRED
        elif report is None or not report.get("invited"):
            state = SiteState.INVITED
        else:
            state = SiteState.MISSING if report.get("stale") else SiteState.PRESENT
        expires = dt.datetime.fromisoformat(entry["expires"])
        row = {"bouquet": bouquet, "state": state.value, "expires": entry["expires"], "issued": entry["issued"],
               "revoked": entry.get("revoked"),
               "expires_soon": state not in (SiteState.REVOKED, SiteState.EXPIRED) and (expires - now).days < SOON_DAYS}
        # someone reporting under an invited bouquet without its token: kept on the site's row until forgotten
        if bouquet in refused:
            row.update(refused_at=refused[bouquet]["time"], reason=refused[bouquet]["reason"])
        rows.append(row)
    for bouquet, attempt in sorted(refused.items()):
        if bouquet in load_registry(port)["invitations"]:
            continue
        rows.append({"bouquet": bouquet, "state": SiteState.UNEXPECTED.value, "refused_at": attempt["time"],
                     "reason": attempt["reason"]})
    return rows


# ************************** command line: session_manager invite | invitations | revoke

COMMANDS = ("invite", "invitations", "revoke")


def cli(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="session_manager", description="Invitations of the lower-level managers (sites)")
    sub = parser.add_subparsers(dest="command", required=True)
    invite = sub.add_parser("invite", help="invite a site: writes invitations/issued/<this bouquet>_downto_<its bouquet>.yml")
    invite.add_argument("--bouquet", required=True, help="the bouquet of the invited site")
    invite.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"validity in days (default {DEFAULT_DAYS})")
    for p in (invite, sub.add_parser("invitations", help="list the invitations"),
              sub.add_parser("revoke", help="revoke a site's invitation")):
        p.add_argument("--port", type=int, default=5555, help="port of the manager inviting (default 5555)")
    invite.add_argument("--url", default=None, help="URL of the manager inviting, as the site reaches it "
                                                    "(default: the one of its last start from this directory)")
    invite.add_argument("--from-bouquet", default=None, help="bouquet of the manager inviting (default: its --bouquet)")
    invite.add_argument("--ca", default=None, help=f"CA certificate of the session (default: the manager's --tls-ca, "
                                                   f"else {CA_FILE_DEFAULT})")
    invite.add_argument("--out", default=str(ISSUED_DIR), help=f"directory of the file (default {ISSUED_DIR})")
    sub.choices["revoke"].add_argument("--bouquet", required=True, help="the bouquet of the site")
    args = parser.parse_args(argv)
    try:
        if args.command == "invite":
            invitation, path = issue(args.port, args.bouquet, args.days, args.url, args.from_bouquet, args.ca, Path(args.out))
            print(f"📨 {path}: invitation of '{invitation.bouquet}', valid until {invitation.expires:%Y-%m-%d}. "
                  f"Hand it to the site's operator only (it holds a token).")
        elif args.command == "revoke":
            revoke(args.port, args.bouquet)
            print(f"✗ invitation of '{args.bouquet}' revoked: the manager on port {args.port} refuses it from now on")
        else:
            entries = load_registry(args.port)["invitations"]
            if not entries:
                print(f"no invitation issued by the manager on port {args.port} from this directory")
            for bouquet, entry in sorted(entries.items()):
                status = "revoked" if entry.get("revoked") else "expired" if _expired(entry) else "active"
                print(f"{bouquet:24} {status:8} until {entry['expires'][:10]}  (issued {entry['issued'][:10]})")
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    return 0
