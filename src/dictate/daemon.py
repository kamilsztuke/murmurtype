import logging
import os
import signal
import socket
import threading
from enum import Enum

from dictate.config import Config
from dictate.notify import Notifier
from dictate.output import deliver
from dictate.paths import socket_path
from dictate.recorder import Recorder, SilenceDetector, StopReason
from dictate.transcriber import Transcriber

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class Daemon:
    def __init__(self, config: Config):
        self.config = config
        self.transcriber = Transcriber(config)
        self.notifier = Notifier(config.notifications)
        self.state = State.IDLE
        self._state_lock = threading.Lock()
        self._recorder: Recorder | None = None

    def handle(self, command: str) -> str:
        match command:
            case "toggle":
                return self.toggle()
            case "start":
                return self.start()
            case "stop":
                return self.stop(StopReason.MANUAL)
            case "cancel":
                return self.stop(StopReason.CANCELLED)
            case "status":
                return self.state.value
            case _:
                return f"error: unknown command {command!r}"

    def toggle(self) -> str:
        with self._state_lock:
            state = self.state
        if state == State.IDLE:
            return self.start()
        if state == State.RECORDING:
            return self.stop(StopReason.MANUAL)
        self.notifier.show("Trwa transkrypcja…", "Poczekaj na wynik poprzedniego dyktowania.")
        return "busy"

    def start(self) -> str:
        with self._state_lock:
            if self.state != State.IDLE:
                return f"error: already {self.state.value}"
            self._recorder = Recorder(SilenceDetector(
                threshold_db=self.config.silence_threshold_db,
                silence_seconds=self.config.silence_seconds,
                no_speech_timeout_seconds=self.config.no_speech_timeout_seconds,
                max_seconds=self.config.max_seconds,
            ))
            self.state = State.RECORDING
        threading.Thread(target=self._run_session, args=(self._recorder,), daemon=True).start()
        return "recording"

    def stop(self, reason: StopReason) -> str:
        with self._state_lock:
            if self.state != State.RECORDING or self._recorder is None:
                return f"error: not recording ({self.state.value})"
            self._recorder.request_stop(reason)
        return "stopping"

    def _set_state(self, state: State):
        with self._state_lock:
            self.state = state
            if state == State.IDLE:
                self._recorder = None

    def _run_session(self, recorder: Recorder):
        try:
            self.notifier.show("Słucham…", "Mów. Skończę po chwili ciszy albo po ponownym skrócie.")
            recording = recorder.record()
            log.info("Recording stopped: %s (%.1fs)", recording.reason.value, recording.audio.size / 16000)

            if recording.reason == StopReason.CANCELLED:
                self.notifier.show("Anulowano", icon="process-stop")
                return
            if recording.reason == StopReason.RECORDER_FAILED:
                self.notifier.show("Błąd nagrywania", "pw-record zakończył się nieoczekiwanie.", icon="dialog-error")
                return
            if not recording.heard_speech:
                self.notifier.show("Nic nie usłyszałem", icon="microphone-sensitivity-muted")
                return

            self._set_state(State.TRANSCRIBING)
            self.notifier.show("Rozpoznaję…", icon="system-run")
            text = self.transcriber.transcribe(recording.audio)
            if not text:
                self.notifier.show("Nie rozpoznano tekstu", icon="dialog-warning")
                return
            deliver(text, self.config)
            self.notifier.show("Wklejono", text, icon="edit-paste")
        except Exception as error:
            log.exception("Dictation session failed")
            self.notifier.show("Błąd dyktowania", str(error), icon="dialog-error")
        finally:
            self._set_state(State.IDLE)


def serve(config: Config):
    daemon = Daemon(config)
    daemon.transcriber.preload()

    path = socket_path()
    path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    path.chmod(0o600)
    server.listen()
    log.info("Listening on %s", path)

    def shutdown(signal_number, frame):
        path.unlink(missing_ok=True)
        # os._exit instead of SystemExit: a second signal arriving during interpreter
        # shutdown would otherwise raise inside threading._shutdown. Worker threads
        # hold nothing that needs flushing.
        os._exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        connection, _ = server.accept()
        with connection:
            command = connection.recv(256).decode("utf-8", errors="replace").strip()
            response = daemon.handle(command)
            connection.sendall(response.encode("utf-8"))
