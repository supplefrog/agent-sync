"""Hermes plugin registration for foreground context routing."""


def register(ctx):
    ctx.register_auxiliary_task(
        key="foreground_context_routing",
        display_name="Foreground context routing",
        description="Choose normal versus extended-context Desktop conversations",
        defaults={
            "provider": "openai-codex",
            "model": "gpt-5.6-luna",
            "timeout": 30,
        },
    )
