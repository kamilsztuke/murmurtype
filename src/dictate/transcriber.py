import gc
import logging
import os
import threading
import time

import numpy
from faster_whisper import WhisperModel

from dictate import cuda
from dictate.config import Config, Device

log = logging.getLogger(__name__)


class Transcriber:
    """Owns the Whisper models and picks CPU or GPU per request.

    In auto mode the CPU model stays loaded permanently, while the GPU model is
    loaded only when enough VRAM is free and is unloaded after an idle period,
    so other GPU workloads get their memory back.
    """

    def __init__(self, config: Config):
        self.config = config
        self._lock = threading.Lock()
        self._cpu_model: WhisperModel | None = None
        self._cuda_model: WhisperModel | None = None
        self._unload_timer: threading.Timer | None = None

    def preload(self):
        with self._lock:
            if self.config.device == Device.CUDA:
                self._load_cuda()
            else:
                self._load_cpu()

    def transcribe(self, audio: numpy.ndarray) -> str:
        with self._lock:
            model, device = self._select_model()
            started = time.monotonic()
            segments, _ = model.transcribe(
                audio,
                language=self.config.language or None,
                beam_size=self.config.beam_size,
                initial_prompt=self.config.initial_prompt or None,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            log.info(
                "Transcribed %.1fs of audio on %s in %.1fs",
                audio.size / 16000, device, time.monotonic() - started,
            )
            if device == Device.CUDA and self.config.device == Device.AUTO:
                self._schedule_cuda_unload()
            return text

    def _select_model(self) -> tuple[WhisperModel, Device]:
        if self.config.device == Device.CPU:
            return self._load_cpu(), Device.CPU
        if self.config.device == Device.CUDA:
            return self._load_cuda(), Device.CUDA

        if self._cuda_model is not None:
            return self._cuda_model, Device.CUDA
        free_mb = cuda.free_memory_mb()
        if free_mb >= self.config.cuda_min_free_mb:
            try:
                return self._load_cuda(), Device.CUDA
            except Exception:
                log.exception("Loading the GPU model failed, falling back to CPU")
        else:
            log.info("Only %d MB VRAM free, using CPU", free_mb)
        return self._load_cpu(), Device.CPU

    def _load_cpu(self) -> WhisperModel:
        if self._cpu_model is None:
            threads = self.config.cpu_threads or max(1, (os.cpu_count() or 2) // 2)
            log.info("Loading %s on CPU (%s, %d threads)", self.config.model, self.config.cpu_compute_type, threads)
            self._cpu_model = WhisperModel(
                self.config.model,
                device="cpu",
                compute_type=self.config.cpu_compute_type,
                cpu_threads=threads,
            )
        return self._cpu_model

    def _load_cuda(self) -> WhisperModel:
        if self._cuda_model is None:
            log.info("Loading %s on GPU (%s)", self.config.model, self.config.cuda_compute_type)
            self._cuda_model = WhisperModel(
                self.config.model,
                device="cuda",
                compute_type=self.config.cuda_compute_type,
            )
        return self._cuda_model

    def _schedule_cuda_unload(self):
        if self._unload_timer is not None:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(self.config.cuda_idle_unload_seconds, self._unload_cuda)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _unload_cuda(self):
        with self._lock:
            if self._cuda_model is None:
                return
            log.info("Unloading idle GPU model")
            self._cuda_model = None
            gc.collect()
