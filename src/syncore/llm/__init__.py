"""LLM provider abstraction.

Syncore never hardcodes a single LLM. Providers implement a small typed
interface. The default DeterministicProvider needs no API key so the whole
system runs offline; swap in OpenAIProvider via LLM_PROVIDER=openai.
"""
