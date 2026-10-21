# SPDX-License-Identifier: GPL-3.0-or-later

import numpy

from murmurtype.recorder import SilenceDetector, StopReason, level_dbfs

LOUD = -20.0
QUIET = -60.0
CHUNK = 0.1


def make_detector(**overrides):
    settings = dict(
        threshold_db=-40.0, silence_seconds=1.0, no_speech_timeout_seconds=2.0, max_seconds=5.0, warmup_seconds=0.0,
    )
    settings.update(overrides)
    return SilenceDetector(**settings)


def feed_repeatedly(detector, level_db, seconds):
    for _ in range(round(seconds / CHUNK)):
        reason = detector.feed(level_db, CHUNK)
        if reason is not None:
            return reason
    return None


def test_stops_after_silence_following_speech():
    detector = make_detector()
    assert feed_repeatedly(detector, LOUD, 0.5) is None
    assert feed_repeatedly(detector, QUIET, 0.8) is None
    assert feed_repeatedly(detector, QUIET, 0.3) == StopReason.SILENCE


def test_speech_resets_silence_counter():
    detector = make_detector()
    feed_repeatedly(detector, LOUD, 0.3)
    feed_repeatedly(detector, QUIET, 0.8)
    feed_repeatedly(detector, LOUD, 0.1)
    assert feed_repeatedly(detector, QUIET, 0.8) is None


def test_gives_up_without_speech():
    detector = make_detector()
    assert feed_repeatedly(detector, QUIET, 3.0) == StopReason.NO_SPEECH
    assert not detector.heard_speech


def test_stops_at_max_length_during_continuous_speech():
    detector = make_detector()
    assert feed_repeatedly(detector, LOUD, 6.0) == StopReason.MAX_LENGTH


def test_loud_transient_during_warmup_is_not_speech():
    detector = make_detector(warmup_seconds=0.4)
    feed_repeatedly(detector, LOUD, 0.4)
    assert not detector.heard_speech
    assert feed_repeatedly(detector, QUIET, 2.0) == StopReason.NO_SPEECH


def test_zero_silence_seconds_disables_silence_stop():
    detector = make_detector(silence_seconds=0.0)
    feed_repeatedly(detector, LOUD, 0.5)
    assert feed_repeatedly(detector, QUIET, 3.0) is None
    assert feed_repeatedly(detector, QUIET, 2.0) == StopReason.MAX_LENGTH


def test_level_dbfs():
    assert level_dbfs(numpy.zeros(1600, dtype=numpy.float32)) == -120.0
    full_scale = numpy.ones(1600, dtype=numpy.float32)
    assert abs(level_dbfs(full_scale)) < 0.01
