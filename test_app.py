from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
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

    class MockResponse:
        @property
        def content(self):
            return b"audio content"

    with (
        patch("openai.OpenAI"),
        patch("openai.resources.audio.Audio.transcriptions"),
        patch("requests.get", return_value=MockResponse()),
        patch("whatdahell.app.get_request_body") as mock_get_request_body,
    ):
        # Send a POST request to the /whatsapp endpoint
        mock_get_request_body.return_value = (
            form_data,
            MockResponse(),
            MagicMock(),
            MagicMock(),
        )
        response = client.post("/whatsapp", data=form_data)

        # Assert the response status code and content
        assert response.status_code == 200
        assert response.text is not None


def test_whatsapp_webhook_with_422():
    with patch("openai.OpenAI"), patch("openai.resources.audio.Audio.transcriptions"):
        response = client.post("/whatsapp", json={"Body": "Hello, world!"})
        assert response.status_code == 422
        assert "detail" in response.json()


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
        transcription = get_transcription("path_to_file")
        assert transcription is not None


def test_write_adio_content_to_file():
    audio_content = "audio content"
    expected_path_to_file = "/tmp/received_audio.mp3"
    with patch("builtins.open"):
        path_to_file = write_adio_content_to_file(audio_content)
        assert path_to_file == expected_path_to_file
