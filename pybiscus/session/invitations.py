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
from typing import Literal, Optional
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# An invitation lets one lower-level manager (a site) report to an upper-level one under the bouquet
# the upper level chose, with a token of its own, until it expires or is revoked: the session token,
# shared by every participant, let anyone holding it report under any bouquet. An agent's
# invitation does the same for one agent of a manager's session, under the name and role the
# manager chose.

INVITATIONS_DIR = Path("invitations")
ISSUED_DIR = INVITATIONS_DIR / "issued"
RECEIVED_DIR = INVITATIONS_DIR / "received"
REGISTRY_DIR = Path(".pybiscus-cache/invitations")
INVITATION_ENV = "PYBISCUS_INVITATION"
REQUIRE_INVITATION_ENV = "PYBISCUS_REQUIRE_INVITATION"
AGENT_INVITATION_ENV = "PYBISCUS_AGENT_INVITATION"
REQUIRE_AGENT_INVITATION_ENV = "PYBISCUS_REQUIRE_AGENT_INVITATION"
AGENT_ROLES = ("client", "server")
DEFAULT_DAYS = 90
# the expiry is shown as close this many days before
SOON_DAYS = 14
# a bouquet, or an invited agent's name, names the issued file and the registry's entry: no
# separator, no "." or ".."
BOUQUET_NAME = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]+$")
CA_FILE_DEFAULT = Path("certificates/ca/ca.crt")


def valid_bouquet(name) -> bool:
    return isinstance(name, str) and bool(BOUQUET_NAME.match(name))


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _digest(token: str) -> str:
    # only the digest is kept: the registry read by someone else gives no token
    return hashlib.sha256(token.encode()).hexdigest()


def _https_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"an https:// URL expected: {url!r}")
    return url.rstrip("/")


def _name(name):
    if not valid_bouquet(name):
        raise ValueError(f"letters, digits, '.', '_' or '-' expected: {name!r}")
    return name


def _aware_date(when):
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def _pem_certificate(text):
    if "-----BEGIN CERTIFICATE-----" not in text:
        raise ValueError("a PEM certificate expected")
    return text


class Invitation(BaseModel):
    """the file the upper level's operator hands to the site's"""
    model_config = ConfigDict(extra="forbid")

    # absent from the invitations issued before the agents' ones
    kind: Literal["manager"] = Field(default="manager", description="a lower-level manager's invitation")
    upper_url: str = Field(description="the upper-level manager, in HTTPS")
    upper_bouquet: str = Field(description="the upper level's bouquet")
    bouquet: str = Field(description="the bouquet of the invited site, set by the upper level")
    token: str = Field(description="the site's own token, presented to the upper-level manager")
    expires: dt.datetime = Field(description="after this date, the upper level refuses the token")
    ca_certificate: str = Field(description="the CA the upper-level manager's certificate is signed by (PEM)")

    _https = field_validator("upper_url")(_https_url)
    _bouquet = field_validator("bouquet", "upper_bouquet")(_name)
    _aware = field_validator("expires")(_aware_date)
    _pem = field_validator("ca_certificate")(_pem_certificate)


class AgentInvitation(BaseModel):
    """the file a manager's operator hands to an agent's"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["agent"] = Field(description="an agent's invitation")
    manager_url: str = Field(description="the manager the agent registers with, in HTTPS")
    bouquet: Optional[str] = Field(description="the manager's bouquet, None when its session has none")
    agent_name: str = Field(description="the name the agent registers under, set by the manager")
    role: Literal["client", "server"] = Field(description="the role the agent registers with, set by the manager")
    token: str = Field(description="the agent's own token, presented to the manager by the agent and its runs")
    expires: dt.datetime = Field(description="after this date, the manager refuses the token")
    ca_certificate: str = Field(description="the CA the manager's certificate is signed by (PEM)")

    _https = field_validator("manager_url")(_https_url)
    _agent_name = field_validator("agent_name")(_name)
    _aware = field_validator("expires")(_aware_date)
    _pem = field_validator("ca_certificate")(_pem_certificate)

    @field_validator("bouquet")
    @classmethod
    def _bouquet(cls, name):
        return None if name is None else _name(name)


def issued_file_name(upper_bouquet: str, bouquet: str) -> str:
    # not an arrow: '>' is forbidden in Windows file names, '→' damaged by some tools
    return f"{upper_bouquet}_downto_{bouquet}.yml"


def agent_file_name(bouquet: str, agent_name: str) -> str:
    # what launch/agent/received_agent_invitation.sh looks for first
    return f"{bouquet}_agent_{agent_name}.yml"


def _write_secret(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    path.chmod(0o600)


def readable_by_others(path: Path) -> bool:
    return os.name == "posix" and bool(path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


# who reads each kind, and whose operator issues it
_KINDS = {"manager": (Invitation, "session_manager --invitation", "the upper level's operator"),
          "agent": (AgentInvitation, "pybiscus_agent --invitation", "the manager's operator")}


def _read(path, kind: str):
    model, reader, issuer = _KINDS[kind]
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"{path}: {e}")
    given = data.get("kind", "manager") if isinstance(data, dict) else None
    if given != kind and given in _KINDS:
        raise ValueError(f"{path} is an invitation of kind {given}: it is given to {_KINDS[given][1]}")
    try:
        invitation = model.model_validate(data)
    except ValueError as e:
        raise ValueError(f"{path} is not a valid invitation: {e}")
    warnings = []
    if readable_by_others(path):
        warnings.append(f"{path} holds a token and is readable by other users: chmod 600 {path}")
    left = invitation.expires - _now()
    if left.total_seconds() <= 0:
        warnings.append(f"the invitation expired on {invitation.expires:%Y-%m-%d}: ask {issuer} for "
                        f"another one (unless it was extended)")
    elif left.days < SOON_DAYS:
        warnings.append(f"the invitation expires on {invitation.expires:%Y-%m-%d}")
    return invitation, warnings


def read_invitation(path) -> tuple[Invitation, list]:
    """a lower-level manager's invitation and the warnings to show; ValueError when the file is not one"""
    return _read(path, "manager")


def read_agent_invitation(path) -> tuple[AgentInvitation, list]:
    """an agent's invitation and the warnings to show; ValueError when the file is not one"""
    return _read(path, "agent")


def received_invitation() -> Optional[Path]:
    """the only manager's invitation of invitations/received, None without; ValueError with several.
    The agents' invitations may lie there too, each named after its agent"""
    if not RECEIVED_DIR.is_dir():
        return None
    files = sorted(p for p in RECEIVED_DIR.iterdir()
                   if p.is_file() and p.suffix in (".yml", ".yaml") and "_downto_" in p.name)
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
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    # invitations: the lower-level managers', by bouquet; agents: the agents', by name
    for section in ("manager", "invitations", "agents"):
        data.setdefault(section, {})
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


def _issuer(data: dict, port: int, url: Optional[str], ca: Optional[str]) -> tuple[str, str]:
    """the URL the invitation names and its CA's text"""
    manager = data["manager"]
    if manager and not manager.get("https") and url is None:
        raise ValueError(f"the manager on port {port} serves HTTP: the token would travel in clear at each contact. "
                         f"Start it with --tls-cert / --tls-key")
    url = url or manager.get("url")
    if not url:
        raise ValueError(f"no manager started on port {port} from this directory: give its URL (--url)")
    ca_path = Path(ca or manager.get("ca") or CA_FILE_DEFAULT)
    if not ca_path.is_file():
        raise ValueError(f"no CA certificate {ca_path}: give the session's CA (--ca certificates/ca/ca.crt)")
    return url, ca_path.read_text(encoding="utf-8")


def _check_days(days) -> None:
    if not isinstance(days, int) or days < 1:
        raise ValueError(f"a number of days of at least 1 expected: {days!r}")


def _entry(token: str, expires: dt.datetime, **fields) -> dict:
    return {"digest": _digest(token), "expires": expires.isoformat(),
            "issued": _now().replace(microsecond=0).isoformat(), "revoked": None, **fields}


def _expiry(days: int) -> dt.datetime:
    return (_now() + dt.timedelta(days=days)).replace(microsecond=0)


def issue(port: int, bouquet: str, days: int = DEFAULT_DAYS, url: Optional[str] = None,
          upper_bouquet: Optional[str] = None, ca: Optional[str] = None, out_dir: Path = ISSUED_DIR) -> tuple[Invitation, Path]:
    """a new invitation for the bouquet, replacing the one it had; the file written"""
    if not valid_bouquet(bouquet):
        raise ValueError(f"bouquet {bouquet!r}: letters, digits, '.', '_' or '-' only")
    _check_days(days)
    with _locked(port):
        data = load_registry(port)
        url, ca_text = _issuer(data, port, url, ca)
        upper_bouquet = upper_bouquet or data["manager"].get("bouquet") or f"manager-{port}"
        token, expires = secrets.token_urlsafe(32), _expiry(days)
        invitation = Invitation(upper_url=url, upper_bouquet=upper_bouquet, bouquet=bouquet, token=token,
                                expires=expires, ca_certificate=ca_text)
        data["invitations"][bouquet] = _entry(token, expires)
        _save_registry(port, data)
    path = out_dir / issued_file_name(upper_bouquet, bouquet)
    _write_secret(path, invitation_text(invitation))
    return invitation, path


def issue_agent(port: int, agent_name: str, role: str = "client", days: int = DEFAULT_DAYS, url: Optional[str] = None,
                bouquet: Optional[str] = None, ca: Optional[str] = None, out_dir: Path = ISSUED_DIR) -> tuple[AgentInvitation, Path]:
    """a new invitation for the agent, replacing the one it had; the file written"""
    if not valid_bouquet(agent_name):
        raise ValueError(f"agent {agent_name!r}: letters, digits, '.', '_' or '-' only")
    if role not in AGENT_ROLES:
        raise ValueError(f"role {role!r}: {' or '.join(AGENT_ROLES)} expected")
    _check_days(days)
    with _locked(port):
        data = load_registry(port)
        url, ca_text = _issuer(data, port, url, ca)
        bouquet = bouquet or data["manager"].get("bouquet")
        token, expires = secrets.token_urlsafe(32), _expiry(days)
        invitation = AgentInvitation(kind="agent", manager_url=url, bouquet=bouquet, agent_name=agent_name, role=role,
                                     token=token, expires=expires, ca_certificate=ca_text)
        data["agents"][agent_name] = _entry(token, expires, role=role)
        _save_registry(port, data)
    path = out_dir / agent_file_name(bouquet or f"manager-{port}", agent_name)
    _write_secret(path, invitation_text(invitation))
    return invitation, path


def invitation_text(invitation) -> str:
    if isinstance(invitation, AgentInvitation):
        head = (f"# Invitation of the agent '{invitation.agent_name}' ({invitation.role}) by the manager {invitation.manager_url}"
                f"{f' ({invitation.bouquet})' if invitation.bouquet else ''},\n"
                f"# valid until {invitation.expires:%Y-%m-%d}. It holds a token: hand it to the agent's operator only,\n"
                f"# who puts it in invitations/received/ (or gives it with pybiscus_agent --invitation). Never commit it.\n")
    else:
        head = (f"# Invitation of the site '{invitation.bouquet}' by '{invitation.upper_bouquet}' ({invitation.upper_url}),\n"
                f"# valid until {invitation.expires:%Y-%m-%d}. It holds a token: hand it to the site's operator only,\n"
                f"# who puts it in invitations/received/ (or gives it with --invitation). Never commit it.\n")
    return head + yaml.safe_dump(json.loads(invitation.model_dump_json()), sort_keys=False, width=200)


def revoke(port: int, bouquet: str, section: str = "invitations") -> None:
    """section: invitations (a site's, by bouquet) or agents (by name)"""
    with _locked(port):
        data = load_registry(port)
        entry = data[section].get(bouquet)
        if entry is None:
            raise ValueError(f"no invitation for {bouquet!r}")
        entry["revoked"] = _now().replace(microsecond=0).isoformat()
        _save_registry(port, data)


def forget(port: int, bouquet: str, section: str = "invitations") -> None:
    with _locked(port):
        data = load_registry(port)
        data[section].pop(bouquet, None)
        _save_registry(port, data)


def _expired(entry: dict) -> bool:
    return dt.datetime.fromisoformat(entry["expires"]) <= _now()


def active(entry: Optional[dict]) -> bool:
    return bool(entry) and not entry.get("revoked") and not _expired(entry)


def _holder(port: int, token: Optional[str], section: str) -> Optional[tuple[str, dict]]:
    """the key and entry whose invitation holds this token, active or not"""
    if not token:
        return None
    digest = _digest(token)
    for key, entry in load_registry(port)[section].items():
        if secrets.compare_digest(entry["digest"], digest):
            return key, entry
    return None


def _problem(port: int, token: Optional[str], section: str) -> Optional[str]:
    held = _holder(port, token, section)
    if held is None or active(held[1]):
        return None
    key, entry = held
    return (f"the invitation of {key} was revoked" if entry.get("revoked")
            else f"the invitation of {key} expired on {entry['expires'][:10]}")


def invited_bouquet(port: int, token: Optional[str]) -> Optional[str]:
    """the bouquet whose active invitation holds this token, None otherwise"""
    held = _holder(port, token, "invitations")
    return held[0] if held and active(held[1]) else None


def invitation_problem(port: int, token: Optional[str]) -> Optional[str]:
    """why this token, an invitation's, is no longer accepted; None if it is not one"""
    return _problem(port, token, "invitations")


def has_active_invitation(port: int, bouquet: str) -> bool:
    return active(load_registry(port)["invitations"].get(bouquet))


def invited_agent(port: int, token: Optional[str]) -> Optional[dict]:
    """{"name", "role"} of the agent whose active invitation holds this token, None otherwise"""
    held = _holder(port, token, "agents")
    return {"name": held[0], "role": held[1]["role"]} if held and active(held[1]) else None


def agent_invitation_problem(port: int, token: Optional[str]) -> Optional[str]:
    """why this token, an agent's invitation's, is no longer accepted; None if it is not one"""
    return _problem(port, token, "agents")


def reserved_agent(port: int, name: str) -> Optional[str]:
    """the role of the agent invited under this name, None when the name is free: an invited name
    is not registered with the session token"""
    entry = load_registry(port)["agents"].get(name)
    return entry["role"] if active(entry) else None


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


class ParticipantState(str, enum.Enum):
    """an agent of the manager's participants page; the page reads the icons and texts from here"""
    INVITED = "invited"         # not registered yet
    REGISTERED = "registered"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REFUSED = "refused"         # came without an invitation, under --require-agent-invitation or an invited name
    ADMITTED = "admitted"       # registered with the session token, not invited


PARTICIPANT_STATE_ICON = {ParticipantState.INVITED: "⏳", ParticipantState.REGISTERED: "✓",
                          ParticipantState.EXPIRED: "⌛", ParticipantState.REVOKED: "✗",
                          ParticipantState.REFUSED: "⛔", ParticipantState.ADMITTED: "○"}
PARTICIPANT_STATE_TEXT = {ParticipantState.INVITED: "invited, not registered yet",
                          ParticipantState.REGISTERED: "registered with its invitation",
                          ParticipantState.EXPIRED: "invitation expired", ParticipantState.REVOKED: "invitation revoked",
                          ParticipantState.REFUSED: "came without invitation, refused",
                          ParticipantState.ADMITTED: "registered with the session token, no invitation"}


def participant_state_protocol() -> dict:
    return {state.value: {"icon": PARTICIPANT_STATE_ICON[state], "text": PARTICIPANT_STATE_TEXT[state]}
            for state in ParticipantState}


def participants(port: int, registered: dict, refused: dict) -> list:
    """the invited agents, the ones registered without an invitation and the refused ones, as the
    page lists them. registered: name -> role; refused: name -> {"time", "reason"}"""
    rows = []
    now = _now()
    invited = load_registry(port)["agents"]
    for name, entry in sorted(invited.items()):
        if entry.get("revoked"):
            state = ParticipantState.REVOKED
        elif _expired(entry):
            state = ParticipantState.EXPIRED
        else:
            state = ParticipantState.REGISTERED if name in registered else ParticipantState.INVITED
        expires = dt.datetime.fromisoformat(entry["expires"])
        row = {"name": name, "role": entry["role"], "state": state.value, "expires": entry["expires"],
               "issued": entry["issued"], "revoked": entry.get("revoked"),
               "expires_soon": state not in (ParticipantState.REVOKED, ParticipantState.EXPIRED)
                               and (expires - now).days < SOON_DAYS}
        # someone registering under an invited name without its token: kept on the agent's row until cleared
        if name in refused:
            row.update(refused_at=refused[name]["time"], reason=refused[name]["reason"])
        rows.append(row)
    for name, role in sorted(registered.items()):
        if name not in invited:
            rows.append({"name": name, "role": role, "state": ParticipantState.ADMITTED.value})
    for name, attempt in sorted(refused.items()):
        if name not in invited and name not in registered:
            rows.append({"name": name, "role": attempt.get("role"), "state": ParticipantState.REFUSED.value,
                         "refused_at": attempt["time"], "reason": attempt["reason"]})
    return rows


# ************************** command line: session_manager invite | invitations | revoke

COMMANDS = ("invite", "invitations", "revoke")


def cli(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="session_manager",
                                     description="Invitations of the lower-level managers (sites) and of the agents")
    sub = parser.add_subparsers(dest="command", required=True)
    invite = sub.add_parser("invite", help="invite a site: writes invitations/issued/<this bouquet>_downto_<its bouquet>.yml; "
                                           "or an agent: invitations/issued/<this bouquet>_agent_<its name>.yml")
    revoke_parser = sub.add_parser("revoke", help="revoke a site's or an agent's invitation")
    for p, what in ((invite, "invited"), (revoke_parser, "whose invitation is revoked")):
        who = p.add_mutually_exclusive_group(required=True)
        who.add_argument("--bouquet", help=f"the bouquet of the site {what}")
        who.add_argument("--agent", help=f"the name of the agent {what}")
    invite.add_argument("--role", choices=AGENT_ROLES, default="client", help="with --agent: its role (default client)")
    invite.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"validity in days (default {DEFAULT_DAYS})")
    for p in (invite, sub.add_parser("invitations", help="list the invitations"), revoke_parser):
        p.add_argument("--port", type=int, default=5555, help="port of the manager inviting (default 5555)")
    invite.add_argument("--url", default=None, help="URL of the manager inviting, as the site or the agent reaches it "
                                                    "(default: the one of its last start from this directory)")
    invite.add_argument("--from-bouquet", default=None, help="bouquet of the manager inviting (default: its --bouquet)")
    invite.add_argument("--ca", default=None, help=f"CA certificate of the session (default: the manager's --tls-ca, "
                                                   f"else {CA_FILE_DEFAULT})")
    invite.add_argument("--out", default=str(ISSUED_DIR), help=f"directory of the file (default {ISSUED_DIR})")
    args = parser.parse_args(argv)
    try:
        if args.command == "invite" and args.agent:
            invitation, path = issue_agent(args.port, args.agent, args.role, args.days, args.url, args.from_bouquet,
                                           args.ca, Path(args.out))
            print(f"📨 {path}: invitation of the agent '{invitation.agent_name}' ({invitation.role}), valid until "
                  f"{invitation.expires:%Y-%m-%d}. Hand it to the agent's operator only (it holds a token).")
        elif args.command == "invite":
            invitation, path = issue(args.port, args.bouquet, args.days, args.url, args.from_bouquet, args.ca, Path(args.out))
            print(f"📨 {path}: invitation of '{invitation.bouquet}', valid until {invitation.expires:%Y-%m-%d}. "
                  f"Hand it to the site's operator only (it holds a token).")
        elif args.command == "revoke":
            revoke(args.port, args.agent or args.bouquet, "agents" if args.agent else "invitations")
            print(f"✗ invitation of '{args.agent or args.bouquet}' revoked: the manager on port {args.port} refuses it from now on")
        else:
            registry = load_registry(args.port)
            if not registry["invitations"] and not registry["agents"]:
                print(f"no invitation issued by the manager on port {args.port} from this directory")
            for title, section, label in (("sites", "invitations", lambda key, entry: key),
                                          ("agents", "agents", lambda key, entry: f"{key} ({entry['role']})")):
                if registry[section]:
                    print(f"{title}:")
                for key, entry in sorted(registry[section].items()):
                    status = "revoked" if entry.get("revoked") else "expired" if _expired(entry) else "active"
                    print(f"  {label(key, entry):30} {status:8} until {entry['expires'][:10]}  (issued {entry['issued'][:10]})")
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    return 0
