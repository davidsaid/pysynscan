from dataclasses import field
from ipaddress import IPv4Address
from typing import Any, Callable
from time import sleep

from synscan.protocol import *
from synscan.udp import UdpCommunicationsModule

# Constant commands
InitializeBaseCommand: CommandMessage = CommandMessage(command=Command.InitializationDone)
TurnAuxSwitchOn: CommandMessage = CommandMessage(
    command=Command.SetAuxSwitchOnOff,
    channel=Channel.Channel1,
    payload=DataSegment(b'1')
)
TurnAuxSwitchOff: CommandMessage = CommandMessage(
    command=Command.SetAuxSwitchOnOff,
    channel=Channel.Channel1,
    payload=DataSegment(b'0')
)

# All motor position data should be offset by this number, meaning our desired positions should have
#  this number added, and all returned position must have this number subtracted
MotorPositionOffset: int = 0x800000


class MotorStatusField(Enum):
    def __str__(self) -> str:
        return f"{type(self).__name__}.{self.name}"

    def __repr__(self) -> str:
        return str(self)


class MotionMode(MotorStatusField):
    GoTo = 0
    Tracking = 1


class MotionDirection(MotorStatusField):
    Clockwise = 0
    CounterClockwise = 1


class MotionSpeed(MotorStatusField):
    Slow = 0
    Medium = 1
    Fast = 2


@dataclass
class MotorStatus:
    motion_mode: MotionMode
    movement_direction: MotionDirection
    movement_speed: MotionSpeed
    is_running: bool
    is_blocked: bool
    is_initialized: bool
    switch_position: bool


def byte_to_int(b: bytes, index=0) -> int:
    return int(b[index]) - ord(b'0')


class MaximumSpeedExceeded(Exception):
    pass


class MinimumSpeedExceeded(Exception):
    pass


@dataclass
class Motor:
    channel: Channel
    counts_per_revolution: int
    timer_interrupt_frequency: int
    _comm: CommunicationsModule = field(repr=False, compare=False)

    def get_degrees_per_count(self) -> float:
        return 360.0 / self.counts_per_revolution

    def degrees_to_count(self, degrees: float) -> int:
        return int(degrees / self.get_degrees_per_count())

    def count_to_degrees(self, count: int) -> float:
        reduced_angle_count = (count % self.counts_per_revolution)
        return reduced_angle_count * self.get_degrees_per_count()

    def send_command(
            self,
            command: Command,
            payload: DataSegment = DataSegment()) -> MotorControllerMessage:
        msg = CommandMessage(command, self.channel, payload)
        return self._comm.send_command(msg)

    def get_position_degrees(self) -> float:
        position_raw = self.send_command(Command.InquirePosition).payload.to_int()
        return self.count_to_degrees(position_raw - MotorPositionOffset)

    def set_position_degrees(self, position_degrees: float) -> None:
        position_count = self.degrees_to_count(position_degrees) + MotorPositionOffset
        payload = DataSegment.from_int(position_count)
        self.send_command(Command.SetPosition, payload)

    def get_status(self) -> MotorStatus:
        status = self.send_command(
            Command.InquireStatus
        ).payload.to_int()

        motion_mode = MotionMode.Tracking if bool(status & 0x010) else MotionMode.GoTo
        movement_direction = MotionDirection.CounterClockwise if bool(status & 0x020) else MotionDirection.Clockwise
        movement_speed = MotionSpeed.Fast if bool(status & 0x040) else MotionSpeed.Slow

        is_running = bool(status & 0x001)
        is_blocked = bool(status & 0x002)

        is_initialized = bool(status & 0x100)
        level_switch = bool(status & 0x200)

        return MotorStatus(
            motion_mode,
            movement_direction,
            movement_speed,
            is_running,
            is_blocked,
            is_initialized,
            level_switch)

    def set_goto_mode(self, movement_speed: MotionSpeed = MotionSpeed.Fast) -> None:
        # Stop motion before setting goto mode
        self.stop_motion()
        # Default movement speed is fast
        payload = b'02'
        if movement_speed == MotionSpeed.Slow:
            payload = b'80'

        self.send_command(Command.SetMotionMode, DataSegment(payload))

    def set_goto_target_degrees(self, target_degrees: float) -> None:
        desired_position = self.degrees_to_count(target_degrees) + MotorPositionOffset
        self.send_command(Command.SetGotoTarget, DataSegment.from_int(desired_position))

    def get_goto_target_degrees(self) -> float:
        target_position = self.send_command(Command.InquireGotoTargetPosition).payload.to_int()
        return self.count_to_degrees(target_position - MotorPositionOffset)

    def set_tracking_mode(
            self,
            speed: MotionSpeed = MotionSpeed.Slow,
            direction: MotionDirection = MotionDirection.Clockwise) -> None:

        self.stop_motion()

        speed_byte = b'1'
        if speed == MotionSpeed.Fast:
            speed_byte = b'3'

        direction_byte = b'0'
        if direction == MotionDirection.CounterClockwise:
            direction_byte = b'1'

        data_segment = DataSegment(speed_byte + direction_byte)
        self.send_command(Command.SetMotionMode, data_segment)

    def t1_preset_for_speed(self, degrees_per_second: float) -> int:
        counts_per_second = abs(degrees_per_second / self.get_degrees_per_count())
        t1_preset = int(self.timer_interrupt_frequency / counts_per_second)
        if t1_preset < 10:
            raise MaximumSpeedExceeded

        if t1_preset > 0xFFFFFF:
            raise MinimumSpeedExceeded

        return t1_preset

    def set_tracking_speed(self, degrees_per_second: float):
        t1_preset = self.t1_preset_for_speed(degrees_per_second)
        data_segment = DataSegment.from_int(t1_preset)

        self.send_command(Command.SetStepPeriod, data_segment)

    def start_motion(self) -> None:
        self.send_command(Command.StartMotion)

    def stop_motion(self) -> None:
        self.send_command(Command.StopMotion)

    def instant_stop(self) -> None:
        self.send_command(Command.InstantStop)

    def track(self, degrees_per_second: float):
        direction = MotionDirection.Clockwise if degrees_per_second >= 0 else MotionDirection.CounterClockwise
        self.set_tracking_mode(direction=direction)
        self.set_tracking_speed(abs(degrees_per_second))
        self.start_motion()

    @classmethod
    def initialize(
            cls,
            channel: Channel,
            comm: CommunicationsModule) -> 'Motor':
        counts_per_revolution = comm.send_command(
            CommandMessage(Command.InquireCountsPerRevolution, channel)
        ).payload.to_int()

        timer_interrupt_frequency = comm.send_command(
            CommandMessage(Command.InquireTimerInterruptFreq, channel)
        ).payload.to_int()

        return cls(channel, counts_per_revolution, timer_interrupt_frequency, comm)


# Discovers stations in the local network
import ipaddress
import socket
from multiprocessing import Pool

from typing import List
from synscan.motorizedbase import *


@dataclass
class AzGti:
    """
    Contains properties and methods
    """
    comm: CommunicationsModule
    azimuth_motor: Motor
    declination_motor: Motor

    def get_position_degrees(self) -> (float, float):
        return tuple(m.get_position_degrees() for m in self.motors())

    def set_position_degrees(self, position_degrees: (float, float)) -> None:
        for motor, position in zip(self.motors(), position_degrees):
            motor.set_position_degrees(position)

    def start_motion(self):
        for m in self.motors():
            m.start_motion()

    def stop_motion(self):
        for m in self.motors():
            m.stop_motion()

    def set_goto_target_degrees(self, position: (float, float)) -> None:
        # Always stop motion before setting objective
        self.stop_motion()
        for m, p in zip(self.motors(), position):
            m.set_goto_target_degrees(p)

    def get_goto_target_degrees(self) -> (float, float):
        return tuple(m.get_goto_target_degrees() for m in self.motors())

    def set_goto_mode(self, motion_speed: MotionSpeed):
        for m in self.motors():
            m.set_goto_mode(motion_speed)

    def motors(self) -> List[Motor]:
        return [self.azimuth_motor, self.declination_motor]

    def is_running(self):
        return any(m.get_status().is_running for m in self.motors())

    def goto(self,
             coordinate_degrees: (float, float),
             motion_speed: MotionSpeed = MotionSpeed.Fast,
             sample_cadence_seconds: float = 0.5,
             sampling_function: Callable[[None], Any] = None) -> List[Any]:
        self.set_goto_mode(motion_speed)
        self.set_goto_target_degrees(coordinate_degrees)
        self.start_motion()
        samples = list()
        while self.is_running():
            sleep(sample_cadence_seconds)
            if sampling_function is not None:
                samples.append(sampling_function())
        return samples

    def track(self, degrees_per_second: (float, float)) -> None:
        self.stop_motion()
        for motor, speed in zip(self.motors(), degrees_per_second):
            motor.track(speed)

    def set_aux_switch_on(self) -> None:
        self.comm.send_command(TurnAuxSwitchOn)

    def set_aux_switch_off(self) -> None:
        self.comm.send_command(TurnAuxSwitchOff)

    @classmethod
    def wifi_mount(
            cls,
            address: IPv4Address = IPv4Address("192.168.4.1"),
            port: int = 11880,
            timeout_in_seconds: int = 2) -> 'MotorizedBase':
        comm = cls._validate_is_comm(address, port, timeout_in_seconds)
        # Grab the motor attributes
        azimuth = Motor.initialize(Channel.Channel1, comm)
        declination = Motor.initialize(Channel.Channel2, comm)

        return cls(comm, azimuth, declination)

    @classmethod
    def _validate_is_comm(
            cls,
            ip_address: IPv4Address,
            port: int = 11880,
            timeout_in_seconds: float = 0.25) -> UdpCommunicationsModule:
        comm = UdpCommunicationsModule(ip_address, port, timeout_in_seconds)
        # If no exception is raised here, our connection to base is OK
        comm.send_command(InitializeBaseCommand)

        return comm

GoogleDns = "8.8.8.8"
TcpPort = 80


def _get_subnet_addresses() -> List[IPv4Address]:
    """
    Ping the Google DNS just so we can get the local host ip_address
        and return all the valid ip addresses in the same subnet
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((GoogleDns, TcpPort))
        self_ip = f"{s.getsockname()[0]}/24"
        interface = ipaddress.ip_interface(self_ip)
        return list(interface.network.hosts())


def _is_synscan_device(ip_address: IPv4Address, timeout_seconds=0.25) -> bool:
    try:
        AzGti._validate_is_comm(ip_address, timeout_in_seconds=timeout_seconds)
        return True
    except:
        return False


def find_synscan_bases(pool_size: int = -1) -> List[AzGti]:
    hosts = _get_subnet_addresses()

    if pool_size < 1:
        pool_size = len(hosts)
    p = Pool(pool_size)
    flags = p.map(_is_synscan_device, hosts)
    p.close()
    return [AzGti.wifi_mount(ip_address) for ip_address, is_base in zip(hosts, flags) if is_base]
