from ipaddress import IPv4Address

from synscan.motorizedbase import AzGti

mount = AzGti.wifi_mount(IPv4Address("192.168.0.145"))
mount.set_position_degrees((0.0, 0.0))
mount.goto((30.0, 30.0))
mount.goto((0.0, 0.0))
