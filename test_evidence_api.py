"""Read-only integration tests against the real API, with UI-only records in memory.

No receiver activity or outbound alert creation. Records exercise presentation,
not capture or classification. Existing local audio is read without modification.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import api_server


@pytest.fixture
def client():
    # Use the application directly. Do not invoke alert creation or its dispatch tasks.
    old_alerts, old_captures = api_server.ALERTS[:], api_server.CAPTURES[:]
    api_server.ALERTS.clear()
    api_server.CAPTURES.clear()
    try:
        with TestClient(api_server.app) as value:
            yield value
    finally:
        api_server.ALERTS[:] = old_alerts
        api_server.CAPTURES[:] = old_captures


def test_empty_service_does_not_report_receiver_live(client):
    assert client.get('/captures').json() == []
    assert client.get('/stress-alerts').json() == []
    health = client.get('/delivery-health').json()
    assert health['service_status'] == 'reachable'
    assert health['capture']['pipeline_status'] == 'unknown'
    assert health['analysis']['status'] == 'unknown'


def test_alert_evidence_retains_fields_without_dispatch(client):
    row = api_server.AlertRecord(
        id='ui-contract-only', created_at=datetime.now(timezone.utc),
        title='UI contract fixture', description='Not a received transmission',
        signal_type=api_server.SignalType.DISTRESS, severity=api_server.AlertSeverity.INFO,
        frequency_mhz=156.8, confidence=0, transcript='Għajnuna · مساعدة · Aiuto · Help',
        language='mt', audio_url=None, tags=[], metadata={'trigger': 'UI test'},
        source='UI contract fixture',
    )
    api_server.ALERTS.append(row)
    payload = client.get('/alerts/ui-contract-only').json()
    assert payload['transcript'] == row.transcript
    assert payload['confidence'] == 0
    evidence = client.get('/alerts/ui-contract-only/evidence').json()
    assert evidence['geography']['position'] is None
    assert evidence['geography']['candidate_tracks'] == []
    answer = client.get('/alerts/ui-contract-only/question?question=why').json()
    assert answer['evidence_fields'] == ['metadata.trigger']
    assert client.get('/alerts/ui-contract-only/question?question=tune').status_code == 400
    assert client.get('/alerts/missing/evidence').status_code == 404


def test_static_routes_are_allowlisted(client):
    for asset in ('dashboard.css', 'dashboard.js', 'evidence-model.mjs', 'vendor/leaflet.js', 'vendor/leaflet.css'):
        response = client.get('/dashboard/' + asset)
        assert response.status_code == 200
    for path in ('/dashboard/../api_server.py', '/dashboard/%2e%2e%2fapi_server.py', '/dashboard/test_evidence_model.mjs'):
        assert client.get(path).status_code == 404
    assert client.get('/').status_code == 200


def test_existing_local_audio_can_be_read(client):
    audio = Path(__file__).parent / 'audio_samples' / 'one_radio_before.mp3'
    if not audio.exists():
        pytest.skip('Local real-audio fixture unavailable; no substitute synthesized')
    response = client.get('/api/audio/one_radio_before.mp3')
    assert response.status_code == 200
    assert response.content == audio.read_bytes()
