"""Development-only browser test runner with in-memory UI records.

Run explicitly with the repository Python environment. No alert creation route,
RF capture, inference, network dispatch, or persistence is invoked. The records
below test presentation only; their text is not a transcript of the audio file.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api_server
import uvicorn

for language, text in [('mt', 'Għajnuna'), ('ar', 'مساعدة'), ('it', 'Aiuto'), ('en', 'Help')]:
    api_server.ALERTS.append(api_server.AlertRecord(
        id='ui-contract-' + language,
        created_at=datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
        title='UI contract fixture · ' + language,
        description='Presentation test only. Text is not a transcript of the recording.',
        signal_type=api_server.SignalType.DISTRESS,
        severity=api_server.AlertSeverity.INFO,
        frequency_mhz=156.8, confidence=0,
        transcript=text + ' <img src=x onerror=alert(1)>', language=language,
        audio_url='/api/audio/one_radio_before.mp3', tags=[],
        metadata={'trigger': 'UI contract test, not an RF detection',
                  'observed_at': '2026-09-09T11:59:00Z',
                  **({'event_location': {'latitude': 35.9, 'longitude': 14.51, 'source': 'UI test coordinates; not an observation'}} if language == 'mt' else {})},
        source='UI contract fixture; not a received transmission',
    ))
api_server.ALERTS.append(api_server.AlertRecord(
    id='ui-contract-threat', created_at=datetime(2026, 9, 9, 13, tzinfo=timezone.utc),
    title='Possible coordinated interference',
    description='Presentation test only. Requires operator review.',
    signal_type=api_server.SignalType.UNKNOWN,
    severity=api_server.AlertSeverity.WARNING,
    frequency_mhz=156.45, confidence=0, transcript=None, language=None,
    audio_url=None, tags=['threat'], source='UI contract fixture',
    metadata={'trigger': 'UI contract test: repeated channel interference'},
))
api_server.CAPTURES.append(api_server.CaptureRecord(
    id='ui-contract-zero', created_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    file_path='UI contract fixture only', frequency_mhz=0, duration_sec=0,
    file_size_mb=0, average_power_dbfs=0, sample_rate_msps=0,
))
if __name__ == '__main__':
    uvicorn.run(api_server.app, host='127.0.0.1', port=3001)
