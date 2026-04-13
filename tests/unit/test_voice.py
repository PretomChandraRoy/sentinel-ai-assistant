from __future__ import annotations

from agent_app.voice.speaker import VoiceSpeaker


def test_speaker_mute_toggle() -> None:
    speaker = VoiceSpeaker()
    assert speaker.muted is False
    result = speaker.toggle_mute()
    assert result is True
    assert speaker.muted is True
    result = speaker.toggle_mute()
    assert result is False
    assert speaker.muted is False


def test_speaker_set_mute() -> None:
    speaker = VoiceSpeaker()
    speaker.set_mute(True)
    assert speaker.muted is True
    speaker.set_mute(False)
    assert speaker.muted is False


def test_speaker_does_not_speak_when_muted() -> None:
    speaker = VoiceSpeaker()
    speaker.set_mute(True)
    # Should not crash or try to create engine when muted
    speaker.speak("Test message")
