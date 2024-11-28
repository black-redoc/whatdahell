import os
from typing import Any
import openai
from fastapi import FastAPI, Request
from fastapi import FastAPI, Request, Form
from starlette.requests import FormData
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml import TwiML
import requests
from requests.auth import HTTPBasicAuth
from langdetect import detect
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)


async def get_request_body(
    request: Request, Body: str = Form(...)
) -> tuple[FormData, MessagingResponse, str, TwiML | str]:
    form = await request.form()
    incoming_msg = Body.strip().lower()
    resp = MessagingResponse()
    msg = resp.message()
    return form, resp, incoming_msg, msg


def get_twilio_response(media_url: str) -> bytes | Any:
    audio_response = requests.get(
        media_url, auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    )
    return audio_response.content


def write_adio_content_to_file(audio_content: bytes) -> str:
    path_to_file = "/tmp/received_audio.mp3"
    with open(path_to_file, "wb") as f:
        f.write(audio_content)
    return path_to_file


def get_transcription(path_to_file: str) -> str:
    audio_file = open(path_to_file, "rb")
    transcript = openai_client.audio.transcriptions.create(
        model="whisper-1", file=audio_file
    )
    transcription = transcript.text
    if len(transcription.split(" ")) > 40:
        transcription = transcription.strip()

        # Detect language of the transcription
        language = detect(transcription)
        # Process transcription with GPT-3.5
        prompt = f"""
        Summarize the following text in no more than 41 words, keeping the summary in {language}:


        Text:
        {transcription}
        """
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        summary = response.choices[0].message.content.strip()
        transcription = summary.split("Summary:")[-1].strip()
    os.remove(path_to_file)
    return transcription


@app.get("/")
async def index(request: Request) -> dict[str, str]:
    return {"hello": "world"}


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request, Body: str = Form(...), NumMedia: str = Form(default="0")
) -> Response:
    (form, resp, _, msg) = await get_request_body(request, Body)

    if int(NumMedia) > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0")

        if "audio" in media_type:
            # Download the audio file
            audio_content = get_twilio_response(media_url)

            # Save the audio file
            path_to_file = write_adio_content_to_file(audio_content)
            try:
                # Transcribe the audio file with Whisper
                response_text = get_transcription(path_to_file)
            except Exception as e:
                print(e)
                response_text = f"Error processing audio: {e}"
        else:
            response_text = f"Invalid media type: {media_type}."
    else:
        response_text = "I'm sorry, I didn't understand that. Send an audio, please. This bot will transcribe it."

    msg.body(response_text)
    return Response(content=str(resp), media_type="application/xml")
