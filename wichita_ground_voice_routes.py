"""HTTP routes for ground voice. Metadata and the audio proxy are separate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

import wichita_ground_voice as gv

router = APIRouter(prefix="/api/ground-voice", tags=["ground-voice"])


@router.get("/channels")
async def channels():
    """Public metadata only. Never includes source URLs."""
    sources = gv.load_private_sources()
    return {"cleared": gv.legally_cleared(),
            "max_total_listeners": gv.LIMITER.total,
            "listeners": gv.LIMITER.count(),
            "channels": gv.channel_status(sources)}


def _limit_response(scope: str) -> JSONResponse:
    return JSONResponse({"state": "listener_limit_reached", "scope": scope,
                         "detail": "Listener limit reached"}, status_code=429)


@router.post("/channels/{channel_id}/ticket")
async def ticket(channel_id: str):
    """Signed-in (Clerk middleware) step that mints a 30 s one-time listen ticket."""
    try:
        gv.get_channel(channel_id)
    except gv.NotAllowed:
        raise HTTPException(404, "Not an allowlisted channel")
    if not gv.legally_cleared() or channel_id not in gv.load_private_sources():
        raise HTTPException(409, "Channel is idle")
    if gv.LIMITER.count(channel_id) >= gv.LIMITER.per_channel:
        return _limit_response("channel")
    if gv.LIMITER.count() >= gv.LIMITER.total:
        return _limit_response("overall")
    return {"ticket": gv.TICKETS.mint(channel_id)}


@router.get("/listen/{channel_id}")
async def listen(channel_id: str, ticket: str = ""):
    """Server-side proxy. The browser gives a channel id, never a URL."""
    try:
        gv.get_channel(channel_id)
    except gv.NotAllowed:
        raise HTTPException(404, "Not an allowlisted channel")
    if not gv.TICKETS.redeem(ticket, channel_id):
        raise HTTPException(401, "Sign in to listen")
    src = gv.load_private_sources().get(channel_id)
    if not gv.legally_cleared() or not src:
        raise HTTPException(409, "Channel is idle")
    try:
        gv.LIMITER.acquire(channel_id)
    except gv.ListenerLimit as e:
        return _limit_response(str(e))

    import httpx

    client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0), follow_redirects=False)
    try:
        upstream = await client.send(client.build_request("GET", src), stream=True)
        if upstream.status_code != 200:
            raise RuntimeError(upstream.status_code)
    except Exception:
        gv.LIMITER.release(channel_id)
        await client.aclose()
        raise HTTPException(502, "Receiver not answering")

    async def body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            gv.LIMITER.release(channel_id)
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(body(), media_type=upstream.headers.get("content-type", "audio/mpeg"),
                             headers={"Cache-Control": "no-store"})
