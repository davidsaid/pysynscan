# Discovers stations in the local network
import ipaddress
import socket

from multiprocessing import Pool
from synscan.comm import comm
from synscan.motors import motors

GOOGLE_DNS_IP_ADDRESS = "8.8.8.8"
TCP_PORT = 80


def get_self_interface():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((GOOGLE_DNS_IP_ADDRESS, TCP_PORT))
        self_ip = f"{s.getsockname()[0]}/24"
        return ipaddress.ip_interface(self_ip)


def is_synscan_device(ip_address, timeout_seconds=2):
    try:
        c = comm(str(ip_address))
        c.timeout_seconds = timeout_seconds
        return c.test_comm()
    except:
        return False


def find_synscan_bases(pool_size=254):
    p = Pool(pool_size)
    hosts = list(get_self_interface().network.hosts())
    base_flags = p.map(is_synscan_device, hosts)
    p.close()
    return [ip_address for ip_address, is_base in zip(hosts, base_flags) if is_base]


if __name__ == '__main__':
    bases = find_synscan_bases()
    for base_ip in bases:
        smc = motors(str(base_ip))
        # Syncronize mount actual position to (0,0)
        smc.set_pos(0, 0)
        # Move forward and wait to finish
        smc.goto(30, 30, syncronous=True)
        # Return to original position and exit without wait
        smc.goto(0, 0, syncronous=False)

