"""Tests for recording URL extraction and end-of-call report merging."""

from src.postcall import _extract_recording_url
from src.webhook_server import _merge_end_of_call_report


class TestExtractRecordingUrl:
    def test_top_level_recording_url(self):
        report = {"recordingUrl": "https://storage.vapi.ai/test-mono.wav"}
        assert _extract_recording_url(report) == "https://storage.vapi.ai/test-mono.wav"

    def test_artifact_recording_mono(self):
        report = {
            "artifact": {
                "recording": {
                    "mono": {"combinedUrl": "https://storage.vapi.ai/mono.wav"},
                }
            }
        }
        assert _extract_recording_url(report) == "https://storage.vapi.ai/mono.wav"

    def test_prefers_recording_url_over_stereo(self):
        report = {
            "recordingUrl": "https://storage.vapi.ai/mono.wav",
            "artifact": {"stereoRecordingUrl": "https://storage.vapi.ai/stereo.wav"},
        }
        assert _extract_recording_url(report) == "https://storage.vapi.ai/mono.wav"


class TestMergeEndOfCallReport:
    def test_message_level_fields_override_empty_call_artifact(self):
        message = {
            "type": "end-of-call-report",
            "call": {
                "id": "call-1",
                "artifact": {},
            },
            "artifact": {
                "recordingUrl": "https://storage.vapi.ai/call-1-mono.wav",
                "transcript": "hello",
            },
            "recordingUrl": "https://storage.vapi.ai/call-1-mono.wav",
        }
        report = _merge_end_of_call_report(message)
        assert report["recordingUrl"] == "https://storage.vapi.ai/call-1-mono.wav"
        assert report["artifact"]["recordingUrl"] == "https://storage.vapi.ai/call-1-mono.wav"
        assert report["artifact"]["transcript"] == "hello"

    def test_message_id_used_when_call_missing_id(self):
        message = {
            "call": {},
            "callId": "call-99",
            "recordingUrl": "https://storage.vapi.ai/x.wav",
        }
        report = _merge_end_of_call_report(message)
        assert report["id"] == "call-99"
