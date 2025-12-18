"""
Whisper Providers Module
รองรับการ switch ระหว่าง Cloud API (Groq) และ On-Premise (whisper.cpp)
"""

from .base_provider import WhisperProvider, TranscriptionResult
from .groq_provider import GroqProvider
from .builtin_provider import BuiltinProvider
from .openai_whisper_provider import OpenAIWhisperProvider
from .faster_whisper_provider import FasterWhisperProvider
from .provider_factory import WhisperProviderFactory, ProviderType

__all__ = [
    'WhisperProvider',
    'TranscriptionResult',
    'GroqProvider',
    'BuiltinProvider',
    'OpenAIWhisperProvider',
    'FasterWhisperProvider',
    'WhisperProviderFactory',
    'ProviderType'
]


