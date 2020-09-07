import synscan
#
'''Goto example'''
mount_ip_address = "192.168.0.143"

smc=synscan.Motors(mount_ip_address)
#Syncronize mount actual position to (0,0)
smc.set_pos(0,0)
#Move forward and wait to finish
smc.goto(30,30,syncronous=True)
#Return to original position and exit without wait
smc.goto(0,0,syncronous=False)
