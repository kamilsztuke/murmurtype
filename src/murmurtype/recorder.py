import logging
import subprocess
import threading
from dataclasses import dataclass
from enum import Enum

import numpy

SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.1
CHUNK_BYTES = int(SAMPLE_RATE * CHUNK_SECONDS) * 2  # 16-bit mono

log = logging.getLogger(__name__)


class StopReason(Enum):
    SILENCE = "silence"
    NO_SPEECH = "no_speech"
    MAX_LENGTH = "max_length"
    MANUAL = "manual"
    CANCELLED = "cancelled"
    RECORDER_FAILED = "recorder_failed"


class SilenceDetector:
    """Decides when to stop recording based on per-chunk loudness."""

    def __init__(
        self,
        threshold_db: float,
        silence_seconds: float,
        no_speech_timeout_seconds: float,
        max_seconds: float,
        warmup_seconds: float = 0.4,
    ):
        self.threshold_db = threshold_db
        # 0 disables stopping on silence: only a manual stop or max_seconds ends the recording.
        self.silence_seconds = silence_seconds
        self.no_speech_timeout_seconds = no_speech_timeout_seconds
        self.max_seconds = max_seconds
        # Microphones (and auto gain control) often emit a loud transient right after
        # the stream opens; counting it as speech would end the recording after
        # `silence_seconds` even if nobody spoke.
        self.warmup_seconds = warmup_seconds
        self.elapsed = 0.0
        self.silent_for = 0.0
        self.heard_speech = False

    def feed(self, level_db: float, duration: float) -> StopReason | None:
        in_warmup = not reached(self.elapsed, self.warmup_seconds)
        self.elapsed += duration
        if in_warmup:
            return None
        if level_db >= self.threshold_db:
            self.heard_speech = True
            self.silent_for = 0.0
        else:
            self.silent_for += duration

        if reached(self.elapsed, self.max_seconds):
            return StopReason.MAX_LENGTH
        if self.silence_seconds > 0 and self.heard_speech and reached(self.silent_for, self.silence_seconds):
            return StopReason.SILENCE
        if not self.heard_speech and reached(self.elapsed, self.no_speech_timeout_seconds):
            return StopReason.NO_SPEECH
        return None


def reached(accumulated: float, limit: float) -> bool:
    # Summing 0.1 s chunks drifts below exact limits (10 * 0.1 == 0.9999...).
    return accumulated >= limit - 1e-6


def level_dbfs(samples: numpy.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = numpy.sqrt(numpy.mean(numpy.square(samples)))
    return float(20 * numpy.log10(max(rms, 1e-6)))


@dataclass
class Recording:
    audio: numpy.ndarray
    reason: StopReason
    heard_speech: bool


class Recorder:
    """Streams microphone audio from pw-record until the detector or a caller stops it."""

    def __init__(self, detector: SilenceDetector):
        self.detector = detector
        self._stop_reason: StopReason | None = None
        self._stop_lock = threading.Lock()

    def request_stop(self, reason: StopReason):
        with self._stop_lock:
            if self._stop_reason is None:
                self._stop_reason = reason

    def _requested_reason(self) -> StopReason | None:
        with self._stop_lock:
            return self._stop_reason

    def record(self) -> Recording:
        process = subprocess.Popen(
            [
                "pw-record",
                "--rate", str(SAMPLE_RATE),
                "--channels", "1",
                "--format", "s16",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        chunks: list[numpy.ndarray] = []
        reason: StopReason | None = None
        try:
            while reason is None:
                reason = self._requested_reason()
                if reason is not None:
                    break
                data = process.stdout.read(CHUNK_BYTES)
                if not data:
                    log.error("pw-record exited unexpectedly (code %s)", process.poll())
                    reason = StopReason.RECORDER_FAILED
                    break
                samples = numpy.frombuffer(data, dtype=numpy.int16).astype(numpy.float32) / 32768.0
                chunks.append(samples)
                reason = self.detector.feed(level_dbfs(samples), samples.size / SAMPLE_RATE)
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

        audio = numpy.concatenate(chunks) if chunks else numpy.zeros(0, dtype=numpy.float32)
        return Recording(audio=audio, reason=reason, heard_speech=self.detector.heard_speech)
