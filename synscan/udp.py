import select
import threading
from ipaddress import IPv4Address
from socket import socket, AF_INET, SOCK_DGRAM
from functools import wraps

from synscan.protocol import *


def retry(exceptions, max_retries=3):
    def retry_decorator(f):
        @wraps(f)
        def func_with_retries(*args, **kwargs):
            _retries = 0
            while _retries < max_retries:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    _retries += 1
                    if _retries >= max_retries:
                        raise

        return func_with_retries

    return retry_decorator


class SynscanSocketTimeoutError(Exception):
    """
    Thrown when a service call to the controller times out
    """
    pass


class UdpCommunicationsModule(CommunicationsModule):
    """
    Implements the CommunicationsModule interface via a UDP socket so we can talk
    to skywatcher wifi mounts.

    TODO: Add logging
    """

    def __init__(self,
                 address: IPv4Address = IPv4Address("192.168.4.1"),
                 port: int = 11880,
                 timeout_in_seconds: int = 2):
        self.address = address
        self.port = port
        self.timeout_in_seconds = timeout_in_seconds
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.setblocking(True)
        self.lock = threading.Lock()

    def __str__(self) -> str:
        return f'{type(self).__name__}(address={self.address}, port={self.port}, timeout_in_seconds={self.timeout_in_seconds})'

    def __repr__(self) -> str:
        return str(self)

    @retry(SynscanSocketTimeoutError)
    def _make_call(self, msg: CommandMessage) -> bytes:
        """
        Make a service call to the telescope base and send the desired command

        @param msg: The message to send
        @return: Raw binary response from the motor
        """
        with self.lock:
            self.socket.sendto(msg.to_bytes(), (str(self.address), self.port))

            ready = select.select([self.socket], [], [], self.timeout_in_seconds)
            if ready[0]:
                response, (_, _) = self.socket.recvfrom(1024)
                return response
            else:
                raise SynscanSocketTimeoutError
