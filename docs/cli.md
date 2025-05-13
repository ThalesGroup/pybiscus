
### Command Line Interface Mode

## Install Pybiscus
After cloning the repo and installing (via uv) all dependencies, you have to extend your PATH with the command:
```bash
source ./extend_path.sh
```

The Pybiscus project comes with an handy app, dubbed pybiscus. You can test it directly :
```bash
pybiscus --help
```

this command will show you some documentation on how to use the app. There are three main commands:
 - server is dedicated to the server side;
 - client, to the client side;
 - local is for local, classical training as a way to compare to the Federated version (if need be)

Note that the package is still actively under development, and even if we try as much as possible to not break things, it could happen!

To work, the app needs only config files for the server and the clients. Any number of clients can be launched, using the same command `client launch`.
or, now with config files (examples are provided in `configs/`):
```bash
pybiscus server launch path-to-config/server.yml
pybiscus client launch path-to-config/client_1.yml
pybiscus client launch path-to-config/client_2.yml
```

You can use also the command `client check` to verify before-hand that the configuration file satisfies the Pydantic constraints.
