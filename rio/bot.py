import os
import sys

from loguru import logger
from pipecat.frames.frames import LLMMessagesFrame, EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams

from pipecat.services.openai import OpenAILLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.vad.silero import SileroVADAnalyzer
from twilio.rest import Client
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.cartesia import CartesiaTTSService

import toml

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

secrets = toml.load(os.path.join(os.path.dirname(__file__), "..", "secrets.toml"))

twilio = Client(secrets["TWILIO_SID"], secrets["TWILIO_KEY"])


async def main(websocket_client, stream_sid):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )

    stt = DeepgramSTTService(api_key=secrets["DEEPGRAM_KEY"])
    llm = OpenAILLMService(
        name="groq",
        api_key=secrets["GROQ_KEY"],
        model="llama-3.2-90b-text-preview",
        base_url="https://api.groq.com/openai/v1",
    )

    tts = CartesiaTTSService(
        api_key=secrets["CARTESIA_KEY"],
        voice_id="95856005-0332-41b0-935f-352e296aa0df",  # Classy British Man
    )

    messages = [
        {
            "role": "system",
            "content": "You are a helpful LLM in an audio call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way.",
        }
    ]

    print("Loaded components...", flush=True)

    context = OpenAILLMContext(messages=messages)
    context_aggregator = llm.create_context_aggregator(context)

    # Create Pipeline
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off conversation
        messages = {
            "role": "system",
            "content": "Please introduce yourself to the user. You're name is Rio.",
        }
        await task.queue_frames([LLMMessagesFrame(messages)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.queue_frames([EndFrame()])

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)
