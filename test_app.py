from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from twilio.twiml.messaging_response import MessagingResponse, Message
import xmltodict

load_dotenv()
from .app import (
    app,
    get_request_body,
    get_transcription,
    get_twilio_response,
    write_adio_content_to_file,
)

client = TestClient(app)


def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}


def test_whatsapp_webhook_with_200():
    # Prepare form data to send with the POST request
    form_data = {
        "Body": "Hello from WhatsApp!",
        "NumMedia": "2",
        "MediaUrl0": "https://example.com/audio.mp3",
        "MediaContentType0": "audio/mp3",
    }
    with patch("openai.OpenAI"):
        # Send a POST request to the /whatsapp endpoint
        response = client.post("/whatsapp", data=form_data)

        # Assert the response status code and content
        assert response.status_code == 200
        result = xmltodict.parse(response.text)
        expeted_result = """
        Error processing audio: Error code: 400 - {'error': {'message': "Invalid file format. Supported formats: ['flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm']", 'type': 'invalid_request_error', 'param': None, 'code': None}}
        """.strip()
        assert result["Response"]["Message"]["Body"] == expeted_result


def test_whatsapp_webhook_with_422():
    response = client.post("/whatsapp", json={"Body": "Hello, world!"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["body", "Body"],
                "msg": "field required",
                "type": "value_error.missing",
            }
        ]
    }


@pytest.mark.asyncio
async def test_get_request_body():
    response_mock = AsyncMock()
    body_mock = "Hello from WhatsApp!"
    expected_msg = "hello from whatsapp!"
    form, resp, incoming_msg, msg = await get_request_body(
        response_mock, Body=body_mock
    )
    assert form is not None
    assert isinstance(resp, MessagingResponse)
    assert incoming_msg == expected_msg
    assert isinstance(msg, Message)


def test_get_twilio_response():
    with patch("requests.get") as mock_get:
        mock_get.return_value.content = b"audio content"
        expected_response = b"audio content"
        response = get_twilio_response("https://example.com/audio.mp3")
        assert response == expected_response


def test_get_transcription():
    with (
        patch("openai.OpenAI") as mock_openai,
        patch("os.remove"),
        patch("builtins.open"),
        patch("openai.resources.audio.Audio.transcriptions"),
        patch(
            "openai.resources.audio.transcriptions.Transcriptions.create"
        ) as mock_transcriptions_create,
    ):
        mock_transcriptions_create.return_value.text = "transcription"
        mock_openai.audio.transcriptions.create.return_value.text = "transcription"
        expected_transcription = "transcription"
        transcription = get_transcription("path_to_file")
        assert transcription == expected_transcription


def test_write_adio_content_to_file():
    audio_content = "audio content"
    expected_path_to_file = "/tmp/received_audio.mp3"
    with patch("builtins.open"):
        path_to_file = write_adio_content_to_file(audio_content)
        assert path_to_file == expected_path_to_file


def test_get_transcription():
    with (
        patch("openai.OpenAI") as mock_openai,
        patch("builtins.open"),
        patch("os.remove"),
        patch("openai.resources.audio.Audio.transcriptions"),
        patch(
            "openai.resources.audio.transcriptions.Transcriptions.create"
        ) as mock_transcriptions_create,
    ):
        mock_transcriptions_create.return_value.text = "transcription"
        mock_openai.audio.transcriptions.create.return_value.text = "transcription"
        expected_transcription = "transcription"
        transcription = get_transcription("path_to_file")
        assert transcription == expected_transcription
