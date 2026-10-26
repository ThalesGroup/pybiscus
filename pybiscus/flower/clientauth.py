"""The Flower clients of a session authenticated by the Flower server: the TLS of Flower's legacy API
authenticates the server only, and any process reaching its port joined the training.

The manager draws a key per session; a client's token is the HMAC of its agent's name under that
key. Each agent asks for its credential with its call token and passes it to its run through the
environment (never in a YAML file, copied into the reports): a client its name and token, the server
the key, which checks the clients registered late too. One connection per name: a participant does
not open several Flower clients."""

import hashlib
import hmac
import os
import threading
from typing import Optional

KEY_ENV = "PYBISCUS_FLOWER_KEY"
CLIENT_ENV = "PYBISCUS_FLOWER_CLIENT"
TOKEN_ENV = "PYBISCUS_FLOWER_TOKEN"
NAME_METADATA = "x-pybiscus-flower-client"
TOKEN_METADATA = "x-pybiscus-flower-token"


def client_token(key_hex: str, name: str) -> str:
    return hmac.new(bytes.fromhex(key_hex), name.encode(), hashlib.sha256).hexdigest()


def server_key() -> Optional[str]:
    return os.environ.get(KEY_ENV) or None


def client_credential() -> Optional[tuple[str, str]]:
    name, token = os.environ.get(CLIENT_ENV), os.environ.get(TOKEN_ENV)
    return (name, token) if name and token else None


def _token_interceptor(key_hex: str):
    import grpc
    import pybiscus.core.pybiscus_logger as logm

    connected, lock = set(), threading.Lock()

    def refuse(reason: str):
        def handler(request_iterator, context):
            logm.console.log(f"⛔ Flower client refused ({context.peer()}): {reason}")
            context.abort(grpc.StatusCode.UNAUTHENTICATED, f"refused by the session's Flower server: {reason}")
        return grpc.stream_stream_rpc_method_handler(handler)

    class TokenInterceptor(grpc.ServerInterceptor):

        def intercept_service(self, continuation, details):
            metadata = dict(details.invocation_metadata or ())
            name, token = metadata.get(NAME_METADATA), metadata.get(TOKEN_METADATA)
            if not name or not token:
                return refuse("no credential of the session (a client launched outside the session?)")
            if not hmac.compare_digest(token.encode(), client_token(key_hex, name).encode()):
                return refuse(f"the credential of {name!r} is not this session's")
            with lock:
                if name in connected:
                    return refuse(f"{name!r} is already connected")
                connected.add(name)
            inner = continuation(details)

            def join(request_iterator, context):
                context.add_callback(lambda: connected.discard(name))
                yield from inner.stream_stream(request_iterator, context)

            return grpc.stream_stream_rpc_method_handler(join, inner.request_deserializer, inner.response_serializer)

    return TokenInterceptor()


def require_client_tokens(key_hex: str) -> None:
    """the next start_server checks the clients' tokens: its gRPC server is created with an
    interceptor, which start_server does not take (to check at each upgrade of flwr)"""
    import flwr.compat.server.app as server_app
    from flwr.proto.transport_pb2_grpc import add_FlowerServiceServicer_to_server
    from flwr.server.superlink.fleet.grpc_bidi.flower_service_servicer import FlowerServiceServicer
    from flwr.supercore.grpc import generic_create_grpc_server

    if not hasattr(server_app, "start_grpc_server"):
        raise RuntimeError("flwr.compat.server.app no longer calls start_grpc_server: the Flower clients cannot be authenticated")
    interceptor = _token_interceptor(key_hex)

    def start_grpc_server(client_manager, server_address, max_message_length, certificates):
        server = generic_create_grpc_server(
            servicer_and_add_fn=(FlowerServiceServicer(client_manager), add_FlowerServiceServicer_to_server),
            server_address=server_address, max_message_length=max_message_length, certificates=certificates,
            interceptors=[interceptor])
        server.start()
        return server

    server_app.start_grpc_server = start_grpc_server


def present_client_token(name: str, token: str) -> None:
    """the next start_client presents this credential: its channel, which start_client creates
    without metadata, is intercepted (to check at each upgrade of flwr)"""
    import collections
    import grpc
    import flwr.compat.client.grpc_client.connection as connection

    if not hasattr(connection, "create_channel"):
        raise RuntimeError("flwr.compat.client.grpc_client.connection no longer calls create_channel: "
                           "the Flower client cannot present its credential")

    class Details(collections.namedtuple("Details", "method timeout metadata credentials wait_for_ready compression"),
                  grpc.ClientCallDetails):
        pass

    class TokenClientInterceptor(grpc.StreamStreamClientInterceptor):

        def intercept_stream_stream(self, continuation, d, request_iterator):
            metadata = [*(d.metadata or ()), (NAME_METADATA, name), (TOKEN_METADATA, token)]
            return continuation(Details(d.method, d.timeout, metadata, d.credentials, d.wait_for_ready,
                                        getattr(d, "compression", None)), request_iterator)

    create_channel = connection.create_channel

    def intercepted_channel(*args, **kwargs):
        return grpc.intercept_channel(create_channel(*args, **kwargs), TokenClientInterceptor())

    connection.create_channel = intercepted_channel
