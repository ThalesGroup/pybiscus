# Invitations

The invitations of the lower-level managers of a hierarchical session (see
[docs/sessionmanager.md](../docs/sessionmanager.md#invitations)) and of the agents of a session
(see [Agents' invitations](../docs/sessionmanager.md#agents-invitations)). Each holds a token:
nothing here but this file and `.gitignore` is ever committed.

- `issued/`: the invitations a manager of this directory issued, each to hand to its operator only:
  - a site's (`session_manager invite --bouquet <site>`, or the 📨 sites page), named
    `<its bouquet>_downto_<the site's bouquet>.yml`;
  - an agent's (`session_manager invite --agent <name> --role <role>`, or the 🎫 participants page),
    named `<its bouquet>_agent_<the agent's name>.yml`.
- `received/`: the invitations received on this machine:
  - this site's manager's, one only: `launch/session/*.sh` start the manager with it
    (`--invitation`) when there is one;
  - the agents', `launch/agent/cli/<port>.sh` starting each agent with its own (`--invitation`): the
    one named after the agent and bouquet of its registration configuration, else the only agent
    invitation there.

Deleting an issued file does not revoke its invitation: `session_manager revoke --bouquet <site>`
or `--agent <name>`, or the manager's page.
