import time
from datetime import datetime
from ipaddress import IPv4Address

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from synscan.motorizedbase import AzGti

exposure_time_seconds = 0.1
scan_range_az = (0.0, 90.0)
scan_range_dec = (0.0, 90.0)
scan_steps_az = 2
scan_steps_dec = 2

mount = AzGti.wifi_mount(IPv4Address("192.168.0.145"))
mount.set_aux_switch_off()
mount.goto((0, 0))

data = []

for dec_degrees in np.linspace(scan_range_dec[0], scan_range_dec[1], scan_steps_dec):
    for az_degrees in np.linspace(scan_range_az[0], scan_range_az[1], scan_steps_az):
        position = (az_degrees, dec_degrees)
        mount.goto(position)
        mount.goto(position)
        time.sleep(exposure_time_seconds)
        mount.set_aux_switch_off()
        data.append(
            (
                np.deg2rad(az_degrees),
                np.deg2rad(dec_degrees),
                datetime.utcnow().isoformat(sep='\n', timespec='milliseconds')
            )
        )
else:
    # Go to home when done
    mount.set_aux_switch_off()
    mount.goto((0, 0))

df = pd.DataFrame(data, columns=['az', 'dec', 'timestamp_utc']).set_index('timestamp_utc')
print(df)


fig, ax = plt.subplots()
df.plot('az', 'dec', kind='scatter', ax=ax)

for k, v in df.iterrows():
    ax.annotate(str(k).replace(" ", "\n"), v, fontsize=8, ha='center', va='center')

plt.grid(True)
plt.show()
