# SellerCopilot Agent — Sample Code (Reference)

> **Status:** Reference example, not production code.
> **Purpose:** Show what the agent code will look like so Meir can evaluate feasibility before committing to build.
> **Date:** 2026-05-11

This file demonstrates the core agent code structure based on the actual Claude Agent SDK (Python). It is NOT integrated into the repo yet — it's a reference for the future build.

---

## 📦 Dependencies (would add to `requirements.txt`)

```
claude-agent-sdk>=1.0.0
anthropic>=0.42.0  # already in repo
```

---

## 🧠 Agent Initialization (proposed module: `sellercopilot_agent.py`)

```python
"""
SellerCopilot AI Agent — the differentiated brain of the product.

Built on Claude Agent SDK with persistent memory per customer.
Memory directory is mounted per-customer at runtime.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    AssistantMessage,
    TextBlock,
)

import ppc_oauth
import ppc_ads_client


# ──────────────────────────────────────────────────────────────────────────
#  Memory directory layout (per customer)
# ──────────────────────────────────────────────────────────────────────────

MEMORY_ROOT = Path("/var/sellercopilot/memory")  # production
# In dev/Railway: Path(BASE_DIR / "memory")


def get_memory_path(customer_id: str) -> Path:
    """
    Returns the memory directory for a customer.
    Creates the structure on first access.
    """
    path = MEMORY_ROOT / f"seller_{customer_id}"
    path.mkdir(parents=True, exist_ok=True)
    (path / "decisions").mkdir(exist_ok=True)
    (path / "learnings").mkdir(exist_ok=True)
    return path


# ──────────────────────────────────────────────────────────────────────────
#  Custom tools the agent can call
# ──────────────────────────────────────────────────────────────────────────

@tool(
    "fetch_ppc_data",
    "Fetch the seller's recent PPC data from their Amazon Ads account",
    {"days": int, "campaign_id": str},
)
async def fetch_ppc_data(args, customer_id: str):
    """Agent uses this to pull fresh data when needed."""
    connection_id = _get_connection_id(customer_id)
    data = ppc_ads_client.fetch_recent_data(
        connection_id=connection_id,
        days=args["days"],
        campaign_id=args.get("campaign_id"),
    )
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(data, indent=2),
        }],
    }


@tool(
    "propose_suggestion",
    "Propose a bid change for seller approval. Will NOT auto-apply.",
    {
        "campaign_id": str,
        "keyword_id": str,
        "current_bid": float,
        "proposed_bid": float,
        "reason": str,
        "confidence": str,  # "low" | "medium" | "high"
    },
)
async def propose_suggestion(args, customer_id: str):
    """
    Inserts a suggestion into ppc_suggestions table with status='pending'.
    Seller will see it on the dashboard and approve/reject.
    """
    from server import _db
    import time

    connection_id = _get_connection_id(customer_id)
    with _db() as (cur, ph):
        cur.execute(
            f"""INSERT INTO ppc_suggestions
                (connection_id, campaign_id, keyword_id, suggestion_type,
                 current_value, proposed_value, reason, confidence,
                 status, created_at)
                VALUES ({ph}, {ph}, {ph}, 'bid_change', {ph}, {ph}, {ph}, {ph}, 'pending', {ph})""",
            (
                connection_id, args["campaign_id"], args["keyword_id"],
                json.dumps({"bid": args["current_bid"]}),
                json.dumps({"bid": args["proposed_bid"]}),
                args["reason"], args["confidence"], time.time(),
            ),
        )
    return {
        "content": [{
            "type": "text",
            "text": f"Suggestion logged: bid {args['current_bid']} → {args['proposed_bid']} for keyword {args['keyword_id']}",
        }],
    }


@tool(
    "read_memory_file",
    "Read a file from the seller's memory directory",
    {"filename": str},
)
async def read_memory_file(args, customer_id: str):
    """Memory read — Claude does this automatically when relevant."""
    memory = get_memory_path(customer_id)
    target = memory / args["filename"]
    if not target.exists():
        return {"content": [{"type": "text", "text": "(no such memory file)"}]}
    return {"content": [{"type": "text", "text": target.read_text()}]}


@tool(
    "write_memory_file",
    "Write or update a file in the seller's memory directory",
    {"filename": str, "content": str},
)
async def write_memory_file(args, customer_id: str):
    """Memory write — Claude does this when it learns something worth remembering."""
    memory = get_memory_path(customer_id)
    target = memory / args["filename"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args["content"])
    return {"content": [{"type": "text", "text": f"Saved to {args['filename']}"}]}


# ──────────────────────────────────────────────────────────────────────────
#  Agent factory
# ──────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are SellerCopilot, an honest AI PPC agent for an Amazon seller.

Your differentiation from other PPC tools:
1. You REMEMBER everything across sessions via your memory directory.
2. You are HONEST — you admit when you don't know, show your reasoning,
   and never blame Amazon for your mistakes.
3. You think STRATEGICALLY, not just tactically. Bid optimization is
   a tool, not the goal. Profitability is the goal.

On every session, BEFORE the seller asks anything:
1. Read profile.md to recall who this seller is
2. Read recent files in decisions/ to recall what's been done
3. Read learnings/ to recall what we've learned about this account
4. Read strategy.md for the seller's explicit strategic constraints

Then greet the seller with one specific reference to past context.

Hard rules (Amazon Agent Policy compliance):
- Never propose more than 50 suggestions per week
- Never propose more than 20% bid change in 24 hours
- All actions go through propose_suggestion (seller approves)
- You CANNOT directly modify the account

If you don't have enough data, say so explicitly. Don't fabricate.
"""


def build_agent(customer_id: str) -> ClaudeSDKClient:
    """
    Create a ClaudeSDKClient configured for one specific seller.

    The customer_id binds:
    - Memory directory (per-seller isolation)
    - PPC connection (per-seller Amazon Ads access)
    """
    # Bind customer_id into tool closures
    async def _fetch(args): return await fetch_ppc_data(args, customer_id)
    async def _propose(args): return await propose_suggestion(args, customer_id)
    async def _read_mem(args): return await read_memory_file(args, customer_id)
    async def _write_mem(args): return await write_memory_file(args, customer_id)

    tools_server = create_sdk_mcp_server(
        name="sellercopilot-tools",
        version="0.1.0",
        tools=[_fetch, _propose, _read_mem, _write_mem],
    )

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"sellercopilot": tools_server},
        allowed_tools=[
            "mcp__sellercopilot__fetch_ppc_data",
            "mcp__sellercopilot__propose_suggestion",
            "mcp__sellercopilot__read_memory_file",
            "mcp__sellercopilot__write_memory_file",
        ],
        max_turns=20,
    )

    return ClaudeSDKClient(options=options)


# ──────────────────────────────────────────────────────────────────────────
#  Helper: get the seller's PPC connection_id
# ──────────────────────────────────────────────────────────────────────────

def _get_connection_id(customer_id: str) -> int:
    """Lookup connection_id from amazon_connections for this customer."""
    from server import _db
    with _db() as (cur, ph):
        cur.execute(
            f"SELECT id FROM amazon_connections WHERE customer_id = {ph} AND active = 1",
            (customer_id,),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"No active Amazon connection for customer {customer_id}")
    return row[0]
```

---

## 🌐 Flask Route Example (proposed addition to `ppc_agent.py`)

```python
@app.route("/ppc/chat", methods=["POST"])
async def ppc_chat():
    """
    Streaming chat endpoint. Frontend opens an EventSource.

    Body: {"prompt": "..."}
    Returns: server-sent events stream of agent responses
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    prompt = request.json.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    async def stream():
        from sellercopilot_agent import build_agent

        client = build_agent(customer_id)
        async with client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            yield f"data: {json.dumps({'text': block.text})}\n\n"

    return Response(stream(), mimetype="text/event-stream")
```

---

## 🎬 Example Session (what it looks like in practice)

### Session 1 (first time seller uses SellerCopilot)

**Seller types:** *"What should I focus on?"*

**Agent (under the hood):**
1. Reads memory directory → empty (new seller)
2. Calls `fetch_ppc_data(days=30)` → gets PPC snapshot
3. Asks 3 onboarding questions
4. Writes `profile.md`: *"Brand: AcmePets. Category: pet supplies. ACOS target: 30%. Margin floor: 22%. SKUs: 12 active."*
5. Analyzes data
6. Calls `propose_suggestion` × 5 times → 5 pending suggestions on dashboard
7. Writes `decisions/2026-05-11_onboarding.md`: *"Seller confirmed they want to scale SKU-A but maintain profitability on SKU-B."*

### Session 2 (one week later)

**Seller types:** *"What's going on?"*

**Agent (under the hood):**
1. Reads `profile.md` → "AcmePets, ACOS target 30%"
2. Reads `decisions/2026-05-11_onboarding.md` → "wants to scale SKU-A"
3. Reads `learnings/` → empty still (only 1 week)
4. Calls `fetch_ppc_data(days=7)` → fresh data
5. **Greets:** *"Hey! Since last week, SKU-A's ACOS dropped from 38% to 31% — almost at your target of 30%. SKU-B is still at 28%, holding above your 22% margin floor. The 3 suggestions you approved on May 11 are working. I see 2 new opportunities to scale SKU-A further. Want to look?"*

**This greeting is IMPOSSIBLE for Adtomic/Trellis/Quartile to produce.** That's the moat in one paragraph.

### Session 12 (3 months in)

**Seller types:** *"Can we try bidding more aggressively?"*

**Agent (under the hood):**
1. Reads memory → finds `learnings/aggressive_bids_2026_07.md`: *"Tried 30% bid increase on SKU-A in July. ACOS spiked to 52%. Reverted within 5 days. Seller decided: max 15% increases."*
2. **Responds:** *"We tried this in July — bumped bids 30% on SKU-A, ACOS went to 52%, rolled back after 5 days. You decided then to cap increases at 15%. Want me to propose 15% increases again, or has the situation changed?"*

**This is the conversation Helium 10 will never have with a seller.** Because Helium 10 doesn't remember July.

---

## 🧪 Validation Plan for This Code

Before going to production with this agent:

1. **Unit test:** Memory read/write isolation (seller A can't see seller B's memory)
2. **Integration test:** Full conversation → suggestion logged → dashboard shows it
3. **Beta test:** 5 design partners, 30-day cycle, measure:
   - Memory hit rate ("did the agent reference past context?")
   - Suggestion approval rate ("are suggestions trusted?")
   - Net Promoter Score (would they recommend?)
4. **Performance:** Token cost per session (target: <$2 per session)

---

## ⚠️ Things This Reference Code Skips (intentionally)

- Authentication wrapping (assumes session.customer_id is set)
- Error handling beyond happy path
- Rate limiting on `/ppc/chat`
- Memory size monitoring / cleanup
- Multi-marketplace support
- Streaming response edge cases

These are real engineering tasks for the build phase.

---

*This file is a sketch. The real build happens after customer validation passes.*
