from dataclasses import dataclass
from enum import Enum


class ConstantMessageSegment(Enum):
    def to_bytes(self) -> bytes:
        return bytes(self.value)

    def __str__(self) -> str:
        return f"{type(self).__name__}.{self.name}"

    def __repr__(self) -> str:
        return str(self)


class Channel(ConstantMessageSegment):
    Channel1 = b'1'
    Channel2 = b'2'
    BothChannels = b'3'


class Command(ConstantMessageSegment):
    SetPosition = b'E'
    InitializationDone = b'F'
    SetMotionMode = b'G'
    SetGotoTarget = b'S'
    SetStepPeriod = b'I'
    StartMotion = b'J'
    StopMotion = b'K'
    InstantStop = b'L'
    SetAuxSwitchOnOff = b'O'
    SetAutoGuideSpeed = b'P'
    RunBootloaderMode = b'Q'
    SetPolarScopeLedBrightness = b'V'
    InquireCountsPerRevolution = b'a'
    InquireTimerInterruptFreq = b'b'
    InquireGotoTargetPosition = b'h'
    InquireStepPeriod = b'i'
    InquirePosition = b'j'
    InquireStatus = b'f'
    InquireHighSpeedRatio = b'g'
    Inquire1XTrackingPeriod = b'D'
    InquireTeleAxisPosition = b'd'
    InquireMotorBoardVersion = b'e'
    ExtendedSetting = b'W'
    ExtendedInquire = b'q'


class ErrorCode(ConstantMessageSegment):
    UnknownCommand = b'0'
    CommandLengthError = b'1'
    MotorNotStopped = b'2'
    InvalidCharacter = b'3'
    NotInitialized = b'4'
    DriverSleeping = b'5'
    PecTrainingIsRunning = b'7'
    NoValidPECdata = b'8'


class MessageHeader(ConstantMessageSegment):
    CommandHeader = b':'
    ResponseHeader = b'='
    ErrorMessageHeader = b'!'

MessageTerminator = b'\r'


def transcode(input: bytes) -> bytes:
    """
    Encodes or decodes the input bytes according to the protocol, used in the data segment of a command or response.
    The examples below show the transform on 24, 16 and 8 bit numbers, written in hexadecimal:
        - 24 bits Data Sample: Input 0x123456 is sent in the order: "56" "34" "12",
            in byte arrays [0x12 , 0x34, 0x56] -> [0x56, 0x34, 0x12]
        - 16 bits Data Sample: Input 0x1234 is sent in the order: "34" "12".
            in byte arrasy [0x12, 0x34] -> [0x34, 0x12]
        - 8 bits Data Sample: Input 0x12 is sent as "12"
    """
    digit_pairs = [input[i:i + 2] for i in range(0, len(input), 2)]
    return b''.join(reversed(digit_pairs))


@dataclass
class DataSegment:
    """
    Represents the data segment of a controller message, it hides the little endian complexit of the protocol from the
    rest of the data model.
    """
    data: bytes = b''

    def to_bytes(self):
        """
        @return: The transcoded byte representation of
        """
        return bytes(transcode(self.data))

    def to_int(self):
        return int(self.data.decode("ascii"), 16)

    @classmethod
    def from_int(cls, value: int) -> 'DataSegment':
        data = bytes("%06X" % value, 'ascii')
        return cls(data)

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> 'DataSegment':
        """
        Create a new data segment from bytes, transcoiding the input data first
        Only use this method to create data segments from payloads received from a motor

        @param raw_data: Raw data that needs to be transcoded before it is made into a segment
        @return:
        """
        return cls(transcode(raw_data[1:-1]))


@dataclass
class CommandMessage:
    """
        The skywatcher protocol is documented in the url below:
        https://inter-static.skywatcher.com/downloads/skywatcher_motor_controller_command_set.pdf


        Pages 3-4 of that document define the
        A command from the master device has the following parts:
            - 1 byte Leading character: ":"
            - 1 byte command word, check command set table for details
            - 1 byte channel word: "1" for RA/Az axis; "2" for Dec/Alt axis.
            - 1 to 6 bytes of data, depending on command word: character "0" to "9", "A" to "F" o 1 byte
            - Ending character: carriage return character.
    """
    command: Command = Command.InquireMotorBoardVersion
    channel: Channel = Channel.BothChannels
    payload: DataSegment = DataSegment()

    def to_bytes(self) -> bytes:
        return MessageHeader.CommandHeader.to_bytes() + \
               self.command.to_bytes() + \
               self.channel.to_bytes() + \
               self.payload.to_bytes() +\
               MessageTerminator


@dataclass
class MotorControllerMessage:
    """
    A normal response from the motor controller has the following parts:
        - 1 byte Leading character: "="
        - 1 to 6 bytes of data, depending on which command is processed: "0" to "9", "A" to "F"
        - 1 byte Ending character: carriage return character.
    An abnormal response from the motor controller has the following parts: o 1 byte Leading character: "!"
        - 2 bytes of error code: "0" to "9", "A" to "F"
        - 1 byte Ending character: carriage return character.
    """
    payload: DataSegment = DataSegment()

    def to_bytes(self) -> bytes:
        return MessageHeader.ResponseHeader.to_bytes() +\
               self.payload.to_bytes() +\
               MessageTerminator

    def decode(self) -> str:
        return str(self.payload)

    def __str__(self) -> str:
        return self.decode()


@dataclass
class MotorControllerError(MotorControllerMessage, Exception):
    """
    This class represents an error returned by a motor controller after a send_message command.

    Being an exception we can and do raise it when the controllers
    """

    def error_code(self) -> ErrorCode:
        return ErrorCode(self.payload.data)

    def decode(self) -> str:
        return self.error_code().name


class CommunicationsModule:
    """
    Abstract communications low level module: defines the public API for
      for a Comm module and will allow us to mock it later for testing or
      to replace our module with one that uses a different interface, say a COM
      port instead of over wifi. For now, the only implementation for this abstract class is UdpCommunicationsModule
    """

    def _make_call(self, msg: CommandMessage) -> bytes:
        """
        Low level API to send a message and receive a binary response, each physical communication device (wifi, com, etc)
        implements this method to abstract away the details of the medium, and returns a raw binary response which will
        be parsed using the static logic on parse_binary_response.

        The send_command API is intended to be the public API for this class

        @param msg: Message to send to the controller
        @return: A binary response that will be parsed according to the synscan protocol
        """
        raise NotImplementedError

    def send_command(self, cmd: CommandMessage) -> MotorControllerMessage:
        """
        @param cmd: Command to send
        @return: The motor response
        """
        response = self._make_call(cmd)
        return CommunicationsModule._parse_binary_response(response)

    @classmethod
    def _parse_binary_response(cls, response: bytes) -> MotorControllerMessage:
        """
        Parse a binary string returned by a motor service call

        @param response: The raw binary response from the controller
        @return: A motor controller message, if the raw data represents an error, then a MotorControllerError is created and
            raised by this method.
        """
        if response[:1] == MessageHeader.ErrorMessageHeader.to_bytes():
            raise MotorControllerError(DataSegment.from_bytes(response))
        elif response[:1] == MessageHeader.ResponseHeader.to_bytes():
            return MotorControllerMessage(DataSegment.from_bytes(response))

        raise TypeError(f"Invalid message {response}")
