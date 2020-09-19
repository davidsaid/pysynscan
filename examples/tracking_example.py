import time

import matplotlib.pyplot as plt
import pandas as pd

from synscan.motorizedbase import *

mount = AzGti.wifi_mount(IPv4Address("192.168.0.145"))


sampling_frequency_seconds = 0.01
time_to_move_seconds = 5
speed_degrees = 3.0

mount.set_position_degrees((180.0, 180.0))
mount.track((speed_degrees, -speed_degrees/2))

data = []
start_time = time.time()
elapsed_seconds = time.time() - start_time
while elapsed_seconds < time_to_move_seconds:
    elapsed_seconds = time.time() - start_time
    az, dec = mount.get_position_degrees()
    data.append(
        (az, dec, elapsed_seconds)
    )
    time.sleep(sampling_frequency_seconds)

mount.stop_motion()

df = pd.DataFrame(
    data,
    columns=['az', 'dec', 'elapsed_seconds']
).set_index('elapsed_seconds')

print(df)

df.plot()
plt.show()

print(df.diff())