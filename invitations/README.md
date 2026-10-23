# Invitations

The invitations of the lower-level managers of a hierarchical session (see
[docs/sessionmanager.md](../docs/sessionmanager.md#invitations)). Each holds a token: nothing here
but this file and `.gitignore` is ever committed.

- `issued/`: the invitations a manager of this directory issued
  (`session_manager invite --bouquet <site>`, or its 📨 sites page), named
  `<its bouquet>_downto_<the site's bouquet>.yml`. Hand each to its site's operator only.
- `received/`: the invitation this site's manager received, one only. `launch/session/*.sh` start
  the manager with it (`--invitation`) when there is one.

Deleting an issued file does not revoke its invitation: `session_manager revoke --bouquet <site>`,
or the sites page.
