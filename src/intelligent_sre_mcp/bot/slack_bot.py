"""
Slack SRE Bot
=============
Bridges Slack with the SRE incident-response agent.

Engineers can trigger investigations and remediations directly from Slack by
mentioning the bot or using the /sre slash command.

Setup
-----
1. Create a Slack app at https://api.slack.com/apps
2. Under "OAuth & Permissions" add bot scopes:
     chat:write, app_mentions:read, commands, channels:history, groups:history
3. Under "Event Subscriptions" enable "app_mention" event
4. Under "Slash Commands" add /sre (request URL: your-server/slack/events)
5. Under "Socket Mode" enable Socket Mode and generate an App-Level Token
   (scope: connections:write)
6. Install the app to your workspace and copy both tokens:
     SLACK_BOT_TOKEN  — Bot User OAuth Token (xoxb-...)
     SLACK_APP_TOKEN  — App-Level Token      (xapp-...)
7. Run::

     python -m intelligent_sre_mcp.bot.slack_bot
     # or
     ./scripts/run-slack-bot.sh

Bot Commands
------------
  /sre <prompt>                 — investigate only (read-only, safe)
  /sre remediate <prompt>       — investigate + apply healing actions
  /sre runbooks                 — list available structured runbooks
  /sre help                     — show this help text

@Mention shortcut
-----------------
  @SRE-Bot <prompt>             -> investigate
  @SRE-Bot --remediate <prompt> -> investigate + remediate

The bot replies in a Slack thread so conversations stay organised.
Responses longer than 3 900 characters are split across multiple messages.

Environment Variables
---------------------
  SLACK_BOT_TOKEN   — (required) Bot User OAuth Token (xoxb-...)
  SLACK_APP_TOKEN   — (required) App-Level Token for Socket Mode (xapp-...)
  ANTHROPIC_API_KEY — (required) Anthropic API key for Claude
  API_URL           — intelligent-sre-agent FastAPI base URL
                      (default: http://localhost:30080)
  SLACK_CHANNEL     — default channel for alert notifications (optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from intelligent_sre_mcp.runbooks import list_runbooks
from intelligent_sre_mcp.sre_agent import run_sre_agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL: str = os.environ.get("API_URL", "http://localhost:30080")
SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN: str = os.environ.get("SLACK_APP_TOKEN", "")

# Slack allows up to 40 000 chars per message; use a conservative chunk size
_CHUNK_SIZE = 3900

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = AsyncApp(token=SLACK_BOT_TOKEN)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_message(text: str, size: int = _CHUNK_SIZE) -> list[str]:
    """Split *text* into chunks of at most *size* chars, breaking at newlines."""
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, size)
        if split_at == -1:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def _send_long(client, channel: str, thread_ts: str, text: str) -> None:
    """Send text to a Slack thread, splitting into multiple messages as needed."""
    for chunk in _split_message(text):
        if chunk.strip():
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=chunk,
            )


def _parse_prompt(text: str) -> tuple[bool, str]:
    """Parse ``remediate`` flag and return (remediate, cleaned_prompt)."""
    text = text.strip()
    remediate = False
    for flag in ("--remediate", "remediate"):
        if text.lower().startswith(flag):
            remainder = text[len(flag) :].strip()
            if remainder:
                return True, remainder
            # flag only — no prompt yet; caller must handle empty prompt
            return True, ""
    return remediate, text


async def _run_incident(
    client,
    channel: str,
    thread_ts: str,
    prompt: str,
    *,
    remediate: bool = False,
) -> None:
    """Run the SRE agent and post results into the given Slack thread."""
    mode_label = "Investigate + Remediate" if remediate else "Investigate"

    await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"*SRE Agent - {mode_label} Mode*\n> {prompt}\nRunning... this may take 30-60 seconds.",
    )

    try:
        result = await run_sre_agent(
            prompt,
            remediate=remediate,
            api_base=API_URL,
        )

        if not result:
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="WARNING: Agent returned an empty response.",
            )
            return

        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="*Agent Response:*",
        )
        await _send_long(client, channel, thread_ts, result)

    except ValueError as exc:
        # Raised when ANTHROPIC_API_KEY is missing
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"ERROR (configuration): {exc}",
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("SRE agent error for prompt=%r", prompt)
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"ERROR: {exc}",
        )


# ---------------------------------------------------------------------------
# Event: @mention
# ---------------------------------------------------------------------------


@app.event("app_mention")
async def handle_mention(event, say, client) -> None:
    """Handle @SRE-Bot <prompt> and @SRE-Bot --remediate <prompt> mentions."""
    # Strip the mention token(s) from the message text
    text: str = event.get("text", "")
    bot_user_id = (await client.auth_test())["user_id"]
    for token in (f"<@{bot_user_id}>",):
        text = text.replace(token, "").strip()

    channel: str = event["channel"]
    # Reply in the same thread if the mention is already inside one
    thread_ts: str = event.get("thread_ts") or event["ts"]

    if not text:
        await say(
            text=(
                "Mention me with a prompt to start an investigation.\n"
                "Example: `@SRE-Bot High 5xx error rate on checkout`\n"
                "Or use `/sre help` for all commands."
            ),
            thread_ts=thread_ts,
        )
        return

    remediate, prompt = _parse_prompt(text)

    if not prompt:
        await say(
            text="Please provide an incident description after `--remediate`.",
            thread_ts=thread_ts,
        )
        return

    # Fire and forget so the mention handler returns immediately
    asyncio.create_task(_run_incident(client, channel, thread_ts, prompt, remediate=remediate))


# ---------------------------------------------------------------------------
# Slash command: /sre
# ---------------------------------------------------------------------------


@app.command("/sre")
async def handle_sre_command(ack, say, command, client) -> None:
    """Handle /sre slash command.

    Sub-commands:
      /sre <prompt>              — investigate
      /sre remediate <prompt>    — investigate + remediate
      /sre --remediate <prompt>  — same as above
      /sre runbooks              — list runbooks
      /sre help                  — show help
    """
    await ack()  # must respond within 3 s

    text: str = (command.get("text") or "").strip()
    channel: str = command["channel_id"]

    if not text or text.lower() == "help":
        await _send_help(say)
        return

    if text.lower() == "runbooks":
        await _send_runbooks(say)
        return

    remediate, prompt = _parse_prompt(text)

    if not prompt:
        await say(
            text="Please provide an incident description. Example: `/sre High 5xx error rate`"
        )
        return

    # Post a placeholder message and use its ts as the thread root
    response = await say(text=f"[{'remediate' if remediate else 'investigate'}] {prompt[:80]}")
    thread_ts: str = response["ts"]

    asyncio.create_task(_run_incident(client, channel, thread_ts, prompt, remediate=remediate))


# ---------------------------------------------------------------------------
# Help and runbooks
# ---------------------------------------------------------------------------


async def _send_help(say) -> None:
    """Post the help text."""
    help_text = (
        "*SRE Bot - Help*\n"
        "AI-powered incident response agent backed by Claude.\n"
        "Integrates with Prometheus, Alertmanager, Kubernetes, and GitHub Issues.\n\n"
        "*Commands:*\n"
        "`/sre <prompt>` — *Investigate only* (read-only, no cluster changes)\n"
        "  Example: `/sre High 5xx error rate on checkout service`\n\n"
        "`/sre remediate <prompt>` or `/sre --remediate <prompt>`\n"
        "  *Investigate + heal* — may restart/scale/rollback pods\n"
        "  Example: `/sre remediate Pods CrashLooping in production`\n\n"
        "`/sre runbooks` — List all structured runbooks\n\n"
        "`@SRE-Bot <prompt>` — Mention to trigger an investigation\n"
        "  Add `--remediate` flag: `@SRE-Bot --remediate Pods crashing`\n\n"
        "_Powered by Claude - intelligent-sre-agent_"
    )
    await say(text=help_text)


async def _send_runbooks(say) -> None:
    """Post the list of available runbooks."""
    runbooks = list_runbooks()
    lines = ["*SRE Runbooks* — Structured playbooks for common production incidents.\n"]
    for rb in runbooks:
        symptoms_preview = "\n".join(f"  - {s}" for s in rb["symptoms"][:3])
        lines.append(f"*{rb['title']}*  (`{rb['name']}`)")
        lines.append(f"{rb['description'][:120]}...")
        lines.append(symptoms_preview)
        lines.append("")
    lines.append("_Tip: `/sre <prompt>` — the agent auto-selects the best matching runbook._")
    await say(text="\n".join(lines))


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Slack SRE bot using Socket Mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not SLACK_BOT_TOKEN:
        print(
            "Error: SLACK_BOT_TOKEN is not set.\nGet a token at https://api.slack.com/apps",
            file=sys.stderr,
        )
        sys.exit(1)

    if not SLACK_APP_TOKEN:
        print(
            "Error: SLACK_APP_TOKEN is not set.\n"
            "Enable Socket Mode in your Slack app and generate an App-Level Token.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info("Starting SRE Slack bot (API_URL=%s) ...", API_URL)

    async def _run() -> None:
        handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
        await handler.start_async()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
