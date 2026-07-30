"""Deterministic byte-level V1 mock device."""

from dataclasses import dataclass

from zeroarm_desktop.protocol.frame_codec import FrameCodec, ProtocolFrame
from zeroarm_desktop.protocol.stream_parser import StreamParser
from zeroarm_desktop.protocol.v1_codec import V1Command, V1ResultCode


@dataclass(frozen=True, slots=True)
class MockFaults:
    drop_response_numbers: frozenset[int] = frozenset()
    corrupt_crc_response_numbers: frozenset[int] = frozenset()
    duplicate_response_numbers: frozenset[int] = frozenset()
    truncate_response_numbers: frozenset[int] = frozenset()
    noise_prefix: bytes = b""


class MockDevice:
    """Consume host V1 bytes and produce deterministic V1 response bytes."""

    def __init__(self, *, faults: MockFaults | None = None) -> None:
        self._parser = StreamParser()
        self._frames = FrameCodec()
        self._faults = faults or MockFaults()
        self._response_number = 0
        self.target_joint_urad = (0, 1_570_770, 0, 0, 0, 0)
        self.actual_joint_urad = (0, 1_570_770, 0, 0, 0, 0)
        self.run_state = 1
        self.enabled_mask = 0
        self.homed_mask = 0
        self.moving_mask = 0
        self.fault_flags = 0

    def receive(self, data: bytes) -> tuple[bytes, ...]:
        responses: list[bytes] = []
        for frame in self._parser.feed(data, received_monotonic_ns=0):
            response = self._handle_frame(frame)
            if response is not None:
                responses.extend(self._apply_faults(response))
        return tuple(responses)

    def _handle_frame(self, frame: ProtocolFrame) -> bytes | None:
        if frame.command == V1Command.HELLO and not frame.payload:
            return self._frames.encode(V1Command.HELLO, b"ZEROARM/1.0")
        if frame.command == V1Command.GET_STATE and not frame.payload:
            self._advance_motion()
            return self._frames.encode(V1Command.GET_STATE, self._state_payload())
        if frame.command == V1Command.SET_JOINT_TARGET and len(frame.payload) == 28:
            self.target_joint_urad = tuple(
                int.from_bytes(frame.payload[index : index + 4], "big", signed=True)
                for index in range(0, 24, 4)
            )  # type: ignore[assignment]
            self.moving_mask = 0x3F
            self.run_state = 4
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.TEACH_START and len(frame.payload) == 1:
            self.run_state = 3
            self.enabled_mask &= ~frame.payload[0]
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.TEACH_STOP and not frame.payload:
            self.run_state = 1
            self.target_joint_urad = self.actual_joint_urad
            return self._result(frame.command, V1ResultCode.OK)
        return self._result(frame.command, V1ResultCode.ERR_NOT_IMPLEMENTED)

    def _advance_motion(self) -> None:
        actual = []
        moving = 0
        for index, (current, target) in enumerate(
            zip(self.actual_joint_urad, self.target_joint_urad, strict=True)
        ):
            difference = target - current
            step = max(-20_000, min(20_000, difference))
            value = current + step
            actual.append(value)
            if value != target:
                moving |= 1 << index
        self.actual_joint_urad = tuple(actual)  # type: ignore[assignment]
        self.moving_mask = moving
        self.run_state = 4 if moving else 1

    def _state_payload(self) -> bytes:
        payload = bytearray(self.run_state.to_bytes(4, "little", signed=True))
        for value in self.target_joint_urad + self.actual_joint_urad:
            payload.extend(value.to_bytes(4, "little", signed=True))
        payload.extend(bytes((self.enabled_mask, self.homed_mask, self.moving_mask, 0)))
        payload.extend(self.fault_flags.to_bytes(4, "little"))
        return bytes(payload)

    def _result(self, command: int, result: V1ResultCode) -> bytes:
        return self._frames.encode(command, bytes((result,)))

    def _apply_faults(self, response: bytes) -> tuple[bytes, ...]:
        self._response_number += 1
        number = self._response_number
        if number in self._faults.drop_response_numbers:
            return ()
        output = self._faults.noise_prefix + response
        if number in self._faults.corrupt_crc_response_numbers:
            corrupted = bytearray(output)
            corrupted[-2] ^= 0x01
            output = bytes(corrupted)
        if number in self._faults.truncate_response_numbers:
            output = output[:-2]
        return (output, output) if number in self._faults.duplicate_response_numbers else (output,)
