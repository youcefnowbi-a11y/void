# -*- coding: utf-8 -*-
"""Verification tests for VOIDFORGE Chat (WarRoom) and Console coordination,
live message fixes, real-time tool event streaming, and UI animations.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

def _read(rel):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, os.pardir, rel), encoding="utf-8") as f:
        return f.read()

def test_server_realtime_tool_event_streaming():
    """Verify server.py defines _broadcast_chat_event and hooks it to ChatSession."""
    server = _read("web/backend/server.py")
    assert "def _broadcast_chat_event(ev: dict):" in server
    assert "asyncio.run_coroutine_threadsafe(manager.broadcast(ev), loop)" in server
    assert "on_event=_broadcast_chat_event" in server
    assert "cs.on_event = _broadcast_chat_event" in server

def test_use_mission_socket_operator_live_message():
    """Verify sendOperatorMessage in useMissionSocket.js immediately appends with isOperatorLive."""
    socket_hook = _read("web/frontend/src/hooks/useMissionSocket.js")
    assert "isOperatorLive: true" in socket_hook
    assert "sendOperatorMessage = useCallback" in socket_hook
    assert "setChatLog(p => [...p, { role: 'user', text: msg, isOperatorLive: true }])" in socket_hook

def test_war_room_operator_live_badge():
    """Verify WarRoom.jsx renders [ORDRE EN DIRECT] badge for live operator messages."""
    war_room = _read("web/frontend/src/components/WarRoom.jsx")
    assert "[ORDRE EN DIRECT]" in war_room
    assert "isLive = m.isOperatorLive" in war_room or "m.isOperatorLive" in war_room

def test_war_room_status_capsule_and_transmission_wave():
    """Verify interactive status capsule and transmission energy wave in WarRoom.jsx and index.css."""
    war_room = _read("web/frontend/src/components/WarRoom.jsx")
    assert "activeRunningTool" in war_room
    assert "transmission-wave" in war_room
    assert "en cours..." in war_room
    assert "onFocusConsole" in war_room

    css = _read("web/frontend/src/index.css")
    assert "@keyframes transmission-wave" in css
    assert ".transmission-wave" in css

def test_live_console_chat_busy():
    """Verify LiveConsole.jsx keeps LIVE badge active during chatBusy."""
    console = _read("web/frontend/src/components/LiveConsole.jsx")
    assert "chatBusy = false" in console
    assert "(status === 'running' || chatBusy)" in console

def test_app_intelligent_console_triggering():
    """Verify App.jsx console triggering, re-arming, Escape handling, and smooth plan exit."""
    app = _read("web/frontend/src/App.jsx")
    assert "hasConsoleActivity = logs.length > 0 || wsStatus !== 'idle'" in app
    assert "setConsolePinned(false)" in app
    assert "setWorkbenchTab('console')" in app
    assert "setConsolePinned(true)" in app
    assert "planExiting" in app
    assert "!e.defaultPrevented" in app

def test_war_room_coordination_and_clean_landing():
    """Verify WarRoom.jsx maintains clean minimalist landing and coordination features."""
    war_room = _read("web/frontend/src/components/WarRoom.jsx")
    assert "activeRunningTool" in war_room
    assert "transmission-wave" in war_room
    assert "isLive" in war_room
    assert "onFocusConsole" in war_room

def test_broadcast_chat_event_functional():
    """Verify _broadcast_chat_event executes correctly with and without running loop."""
    import asyncio
    from web.backend import server

    # Test without loop: fallback to _CHAT_EVENTS
    server._LOOP["loop"] = None
    server._CHAT_EVENTS.clear()
    server._broadcast_chat_event({"type": "tool_start", "tool": "test_scanner"})
    assert len(server._CHAT_EVENTS) == 1
    assert server._CHAT_EVENTS[0]["tool"] == "test_scanner"
    server._CHAT_EVENTS.clear()

    # Test with loop: schedules broadcast task
    async def _test():
        loop = asyncio.get_running_loop()
        server._LOOP["loop"] = loop
        broadcasts = []
        original_broadcast = server.manager.broadcast
        async def mock_broadcast(ev):
            broadcasts.append(ev)
        server.manager.broadcast = mock_broadcast
        try:
            server._broadcast_chat_event({"type": "tool_result", "tool": "test_scanner", "status": "ok"})
            await asyncio.sleep(0.05)
            assert len(broadcasts) == 1
            assert broadcasts[0]["tool"] == "test_scanner"
        finally:
            server.manager.broadcast = original_broadcast
            server._LOOP["loop"] = None

    asyncio.run(_test())

def test_server_operator_live_history_parsing():
    """Verify chat_log route correctly extracts [ORDRE EN DIRECT] prefix into isOperatorLive: True."""
    from web.backend import server

    class MockSession:
        def __init__(self):
            self.history = [
                {"role": "user", "content": "Normal question"},
                {"role": "user", "content": "[ORDRE EN DIRECT] Strike hard on port 80"},
                {"role": "assistant", "content": "Roger that"},
            ]
        def count(self):
            return len(self.history)

    original_session = server._CHAT.get("session")
    server._CHAT["session"] = MockSession()
    try:
        import asyncio
        res = asyncio.run(server.chat_log())
        assert res["status"] == "ok"
        assert len(res["log"]) == 3
        assert res["log"][0]["text"] == "Normal question"
        assert not res["log"][0].get("isOperatorLive")
        assert res["log"][1]["text"] == "Strike hard on port 80"
        assert res["log"][1]["isOperatorLive"] is True
        assert res["log"][2]["role"] == "strategist"
    finally:
        server._CHAT["session"] = original_session

