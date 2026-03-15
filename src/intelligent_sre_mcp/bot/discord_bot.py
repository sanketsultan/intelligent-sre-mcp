"""
Discord SRE Bot
===============
Bridges Discord chat with the SRE incident response agent.

Allows engineers to trigger incident investigations and remediations directly
from Discord by mentioning the bot or using ``!sre`` commands.

Usage
-----
1. Create a Discord application at https://discord.com/developers/applications
2. Add a bot, enable "Message Content Intent" under Privileged Gateway Intents
3. Copy the bot token into DISCORD_BOT_TOKEN env var
4. Invite the bot with scopes: bot + applications.commands, permissions: Send Messages,
   Create Public Threads, Read Message History, Add Reactions
5. Run::

     python -m intelligent_sre_mcp.bot.discord_bot
     # or
     ./scripts/run-discord-bot.sh

Bot Commands
------------
  !sre <prompt>                — Phase 1: investigate only (read-only, safe)
  !sre remediate <prompt>      — Phase 1 + Phase 2: investigate + apply healing
  !sre runbooks                — List all available structured runbooks
  !sre help                    — Show this help

@Mention shortcut
-----------------
  @SRE-Bot <prompt>                   → investigate
  @SRE-Bot --remediate <prompt>       → investigate + remediate

The bot creates a Discord thread per incident so conversations stay organised.
Responses longer than 2 000 characters are split across multiple messages.

Environment Variables
---------------------
  DISCORD_BOT_TOKEN   — (required) Discord bot token
  ANTHROPIC_API_KEY   — (required) Anthropic API key for Claude
  API_URL             — intelligent-sre-mcp FastAPI base URL
                        (default: http://localhost:30080)
  ALERTMANAGER_URL    — Alertmanager URL (default: http://localhost:9093)
  GITHUB_TOKEN        — GitHub personal-access-token for post-mortem issues
  GITHUB_REPO         — GitHub repo in "owner/repo" format
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

from intelligent_sre_mcp.runbooks import list_runbooks
from intelligent_sre_mcp.sre_agent import run_sre_agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL: str = os.environ.get("API_URL", "http://localhost:30080")
DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")

# Discord has a 2 000-character hard limit per message; leave a small buffer
_CHUNK_SIZE = 1900

# ---------------------------------------------------------------------------
# Bot Setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # required to read message text (Privileged Intent)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

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


async def _send_long(dest: discord.abc.Messageable, text: str) -> None:
    """Send text to Discord, splitting into multiple messages as needed."""
    for chunk in _split_message(text):
        if chunk.strip():
            await dest.send(chunk)


async def _keep_typing(channel: discord.abc.Messageable, stop: asyncio.Event) -> None:
    """Re-trigger the typing indicator every 8 s until *stop* is set.

    Discord's typing indicator automatically expires after ~10 s, so we
    refresh it frequently for long-running agent calls.
    """
    while not stop.is_set():
        async with channel.typing():
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=8.0)
        except asyncio.TimeoutError:
            pass  # not stopped yet — loop again


# ---------------------------------------------------------------------------
# Core: Run the SRE Agent and post results to a Discord thread
# ---------------------------------------------------------------------------


async def _run_incident(
    ctx: commands.Context,
    prompt: str,
    *,
    remediate: bool = False,
) -> None:
    """Create a thread, run the SRE agent, and stream the result back."""
    mode_label = "investigate + remediate" if remediate else "investigate"
    header_emoji = "⚕️" if remediate else "🔍"

    # ── Create a thread on the triggering message for clean isolation ────────
    thread_name = f"{header_emoji} {prompt[:80]}"
    try:
        thread: discord.abc.Messageable = await ctx.message.create_thread(
            name=thread_name,
            auto_archive_duration=60,  # archive after 60 min of inactivity
        )
    except (discord.HTTPException, discord.Forbidden):
        # Fallback: reply in the same channel if we cannot create threads
        thread = ctx.channel  # type: ignore[assignment]

    await thread.send(
        f"{header_emoji} **SRE Agent — {mode_label.title()} Mode**\n"
        f"> {prompt}\n"
        f"⏳ Running… this may take 30–60 seconds."
    )

    # ── Keep typing indicator alive while the agent works ────────────────────
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(thread, stop_typing))

    try:
        result = await run_sre_agent(
            prompt,
            remediate=remediate,
            api_base=API_URL,
        )

        stop_typing.set()
        await asyncio.shield(typing_task)  # let it finish cleanly

        if not result:
            await thread.send("⚠️ Agent returned an empty response.")
            return

        done_emoji = "✅" if remediate else "🔎"
        await thread.send(f"{done_emoji} **Agent Response:**")
        await _send_long(thread, result)

    except ValueError as exc:
        # Raised when ANTHROPIC_API_KEY is missing
        stop_typing.set()
        await thread.send(f"❌ **Configuration error:** {exc}")

    except Exception as exc:  # noqa: BLE001
        stop_typing.set()
        logger.exception("SRE agent error for prompt=%r", prompt)
        await thread.send(f"❌ **Unexpected error:** {exc}")

    finally:
        typing_task.cancel()


# ---------------------------------------------------------------------------
# Bot Events
# ---------------------------------------------------------------------------


@bot.event
async def on_ready() -> None:
    logger.info("SRE Discord bot ready | user=%s id=%s", bot.user, bot.user.id)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="production | !sre help",
        )
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle @bot-mention as a shortcut for !sre / !sre remediate."""
    if message.author.bot:
        return

    # Check whether the bot was mentioned
    if bot.user and bot.user in message.mentions:
        # Strip the mention token(s) from the content
        content = message.content
        for mention_str in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            content = content.replace(mention_str, "").strip()

        if not content:
            await message.channel.send(
                f"👋 Mention me with a prompt to start an investigation.\n"
                f"Example: `@{bot.user.display_name} High 5xx error rate on checkout`\n"
                f"Or use `!sre help` for all commands."
            )
            return

        # Detect --remediate flag in the mention content
        remediate = content.startswith("--remediate")
        if remediate:
            content = content[len("--remediate") :].strip()

        ctx = await bot.get_context(message)
        await _run_incident(ctx, content, remediate=remediate)
        return  # skip process_commands — we've handled this

    # Pass all other messages through the command dispatcher
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return  # silently ignore — avoids spam on unrelated ! messages
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Missing argument: `{error.param.name}`. Try `!sre help`.")
    else:
        logger.exception("Discord command error", exc_info=error)
        await ctx.send(f"❌ Error: {error}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@bot.group(name="sre", invoke_without_command=True)
async def sre_group(ctx: commands.Context, *, prompt: str | None = None) -> None:
    """SRE incident response agent.

    Usage: !sre <prompt>           — investigate only
           !sre remediate <prompt> — investigate + remediate
           !sre runbooks           — list runbooks
           !sre help               — show this message
    """
    if not prompt:
        await sre_help_cmd(ctx)
        return

    # Support: !sre --remediate <prompt>  (same as !sre remediate <prompt>)
    remediate = False
    if prompt.startswith("--remediate"):
        remediate = True
        prompt = prompt[len("--remediate") :].strip()

    if not prompt:
        await ctx.send("⚠️ Please provide an incident description after `--remediate`.")
        return

    await _run_incident(ctx, prompt, remediate=remediate)


@sre_group.command(name="remediate")
async def sre_remediate_cmd(ctx: commands.Context, *, prompt: str) -> None:
    """Investigate **and** apply healing actions.

    Example: !sre remediate Pods CrashLooping in the intelligent-sre namespace
    """
    await _run_incident(ctx, prompt, remediate=True)


@sre_group.command(name="runbooks")
async def sre_runbooks_cmd(ctx: commands.Context) -> None:
    """List all available structured runbooks."""
    runbooks = list_runbooks()

    embed = discord.Embed(
        title="📚 SRE Runbooks",
        description="Structured playbooks for common production incidents.",
        color=discord.Color.green(),
    )

    for rb in runbooks:
        symptoms_preview = "\n".join(f"• {s}" for s in rb["symptoms"][:3])
        embed.add_field(
            name=f"**{rb['title']}**  ·  `{rb['name']}`",
            value=f"{rb['description'][:120]}…\n{symptoms_preview}",
            inline=False,
        )

    embed.set_footer(text="Tip: !sre <prompt> — the agent auto-selects the best matching runbook.")
    await ctx.send(embed=embed)


@sre_group.command(name="help")
async def sre_help_cmd(ctx: commands.Context) -> None:
    """Show usage information."""
    embed = discord.Embed(
        title="🔧 SRE Bot — Help",
        description=(
            "AI-powered incident response agent backed by Claude claude-opus-4-6.\n"
            "Integrates with Prometheus, Alertmanager, Kubernetes, and GitHub Issues."
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="`!sre <prompt>`",
        value=(
            "**Investigate only** — read-only, no cluster changes.\n"
            "Example: `!sre High 5xx error rate on checkout service`"
        ),
        inline=False,
    )
    embed.add_field(
        name="`!sre remediate <prompt>`  or  `!sre --remediate <prompt>`",
        value=(
            "**Investigate + heal** — may restart/scale/rollback pods.\n"
            "Example: `!sre remediate Pods CrashLooping in production`"
        ),
        inline=False,
    )
    embed.add_field(
        name="`!sre runbooks`",
        value="List all structured runbooks (DB pool exhaustion, high latency, elevated errors).",
        inline=False,
    )
    embed.add_field(
        name="`@SRE-Bot <prompt>`",
        value=(
            "Mention the bot to trigger an investigation.\n"
            "Add `--remediate` flag: `@SRE-Bot --remediate Pods crashing`"
        ),
        inline=False,
    )
    embed.set_footer(text="Powered by Claude claude-opus-4-6 · intelligent-sre-mcp")
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Discord SRE bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not DISCORD_BOT_TOKEN:
        print(
            "Error: DISCORD_BOT_TOKEN is not set.\n"
            "Get a token at https://discord.com/developers/applications",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info("Starting SRE Discord bot (API_URL=%s) ...", API_URL)
    # log_handler=None uses our basicConfig above instead of discord.py's default
    bot.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
