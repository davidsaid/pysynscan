import time

import matplotlib.pyplot as plt
import pandas as pd

from synscan.motorizedbase import *

mount = AzGti.wifi_mount(IPv4Address("192.168.0.145"))


mount.set_position_degrees((0.0, 0.0))

sampling_frequency_seconds = 0.01
time_to_move_seconds = 5
speed_degrees = 3.0

m = mount.azimuth_motor
m.set_tracking_mode(speed=MotionSpeed.Slow, direction=MotionDirection.CounterClockwise)
m.set_tracking_speed(speed_degrees)
m.start_motion()

data = []
start_time = time.time()
elapsed_seconds = time.time() - start_time
while elapsed_seconds < time_to_move_seconds:
    elapsed_seconds = time.time() - start_time
    az, dec = mount.get_position_degrees()
    data.append(
        (az, dec, elapsed_seconds, speed_degrees)
    )
    time.sleep(sampling_frequency_seconds)

m.stop_motion()

df = pd.DataFrame(
    data,
    columns=['az', 'dec', 'elapsed_seconds', 'speed']
).set_index('elapsed_seconds')

print(df)

df.plot(y='az')
plt.show()

print(df.diff())