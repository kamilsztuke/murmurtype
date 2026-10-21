import logging
import subprocess

log = logging.getLogger(__name__)

APP_NAME = "MurmurType"


class Notifier:
    """Shows desktop notifications, replacing the previous one instead of stacking them."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._notification_id: str | None = None

    def show(self, summary: str, body: str = "", icon: str = "audio-input-microphone"):
        if not self.enabled:
            return
        command = [
            "notify-send",
            "--app-name", APP_NAME,
            "--icon", icon,
            "--urgency", "low",
            "--hint", "boolean:transient:true",
            "--print-id",
        ]
        if self._notification_id:
            command += ["--replace-id", self._notification_id]
        command += [summary, body]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError) as error:
            log.warning("notify-send failed: %s", error)
            return
        self._notification_id = result.stdout.strip() or None
