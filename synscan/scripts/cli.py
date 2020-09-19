#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
#
# pysynscan
# Copyright (c) July 2020 Nacho Mas

import os
import time

import click

from synscan.motorizedbase import AzGti


def configure_mount(ip_address: str, port: int) -> AzGti:
    return AzGti.wifi_mount(
        address=os.getenv("SYNSCAN_UDP_IP", ip_address),
        port=os.getenv("SYNSCAN_UDP_PORT", port)
    )


# GOTO
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.option('--wait', type=bool, help='Wait until finished (default False)', default=False)
@click.argument('azimuth', type=float)
@click.argument('altitude', type=float)
def goto(host, port, azimuth, altitude, wait):
    """Do a GOTO to a target azimuth/altitude"""
    mount = configure_mount(host, port)
    mount.goto((azimuth, altitude))


# TRACK
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.argument('azimuth_speed', type=float)
@click.argument('altitude_speed', type=float)
def track(host, port, azimuth_speed, altitude_speed):
    """Move at desired speed (degrees per second)"""
    mount = configure_mount(host, port)
    mount.track((azimuth_speed, altitude_speed))


# STOP
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.option('--wait', type=bool, help='Wait until finished', default=True)
def stop(host, port, wait):
    """Stop Motors"""
    mount = configure_mount(host, port)
    mount.stop_motion()


# SHOW
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.option('--seconds', type=float, help='Show every N seconds (default 1s)', default=1)
def watch(host, port, seconds):
    """Watch values"""
    mount = configure_mount(host, port)
    while True:
        print("Time:", time.localtime())
        print("Position:", mount.get_position_degrees())
        print("Azimuth motor status:", mount.azimuth_motor.get_status())
        print("Declination motor status:", mount.declination_motor.get_status())
        time.sleep(seconds)


# SYNCRONIZE
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.argument('azimuth', type=float)
@click.argument('altitude', type=float)
def syncronize(host, port, azimuth, altitude):
    """Syncronize actual position with the azimuth/altitude provided"""
    mount = configure_mount(host, port)
    mount.set_position_degrees((azimuth, altitude))


# Set On/off auxiliary switch
@click.command()
@click.option('--host', type=str, help='Synscan mount IP address', default='192.168.4.1')
@click.option('--port', type=int, help='Synscan mount port', default=11880)
@click.option('--seconds', type=float, help='Seconds to automatic deactivation', default=0)
@click.argument('on', type=bool)
def switch(host, port, on, seconds):
    """Activate/Deactivate mount auxiliary switch. ON must be bool (1 or 0)"""
    import time
    mount = configure_mount(host, port)
    toggle = seconds > 0

    if on:
        mount.set_aux_switch_on()
    else:
        mount.set_aux_switch_off()

    if toggle:
        time.sleep(seconds)
        if on:
            mount.set_aux_switch_off()
        else:
            mount.set_aux_switch_on()
