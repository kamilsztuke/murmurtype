import argparse
import logging
import socket
import subprocess
import sys

from murmurtype.notify import APP_NAME
from murmurtype.paths import socket_path

COMMANDS = ["toggle", "start", "stop", "cancel", "status"]


def send(command: str) -> int:
    path = socket_path()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(path))
            client.sendall(command.encode("utf-8"))
            response = client.recv(4096).decode("utf-8")
    except (FileNotFoundError, ConnectionRefusedError):
        message = "Usługa murmurtype nie działa. Uruchom: systemctl --user start murmurtype"
        print(message, file=sys.stderr)
        subprocess.run(["notify-send", "--app-name", APP_NAME, "--icon", "dialog-error", APP_NAME, message])
        return 1
    print(response)
    return 1 if response.startswith("error") else 0


def run_daemon() -> int:
    from murmurtype import cuda
    from murmurtype.config import load_config

    cuda.ensure_library_path()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Hugging Face Hub logs every HTTP request of the model download at INFO level.
    for noisy_logger in ("httpx", "httpx2", "huggingface_hub"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Imported here, not at module level: the client runs on every shortcut press
    # and must not pay for importing faster-whisper.
    from murmurtype.daemon import serve

    serve(load_config())
    return 0


def main():
    parser = argparse.ArgumentParser(prog="murmurtype", description="Whisper dictation for GNOME on Wayland.")
    parser.add_argument("command", choices=["daemon", *COMMANDS])
    arguments = parser.parse_args()
    if arguments.command == "daemon":
        sys.exit(run_daemon())
    sys.exit(send(arguments.command))
