import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, List, MutableMapping, Optional

import streamlit as st
from openai import AsyncOpenAI

try:  # pragma: no cover - compatibility shim for older mcp versions
    from mcp.client.stdio import connect  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    @asynccontextmanager
    async def connect(command: Iterable[str]):  # type: ignore[misc]
        command = list(command)
        if not command:
            raise ValueError("connect() requires at least one command element")

        params = StdioServerParameters(command=command[0], args=list(command[1:]))

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


OPENAI_MODEL = "gpt-4o-mini"
MCP_COMMAND = ["python", "server/server.py"]


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: List[MutableMapping[str, Any]] = []
    if "openai_client" not in st.session_state:
        st.session_state.openai_client = AsyncOpenAI()


async def _get_mcp_client():
    if "mcp_client" not in st.session_state:
        st.session_state.mcp_context = connect(MCP_COMMAND)
        st.session_state.mcp_client = await st.session_state.mcp_context.__aenter__()
        st.session_state.mcp_initialized = False

    if not st.session_state.get("mcp_initialized", False):
        await st.session_state.mcp_client.initialize()
        st.session_state.mcp_initialized = True

    return st.session_state.mcp_client


def _as_openai_messages(messages: Iterable[MutableMapping[str, Any]]) -> List[Dict[str, Any]]:
    openai_messages: List[Dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")

        if role == "tool":
            openai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": message.get("tool_call_id"),
                    "content": content,
                }
            )
            continue

        openai_messages.append({"role": role, "content": content})

    return openai_messages


def _render_history(messages: Iterable[MutableMapping[str, Any]]) -> None:
    for message in messages:
        message_type = message.get("type", message.get("role"))
        content = message.get("content", "")

        if not content:
            continue

        if message_type == "human" or message.get("role") == "user":
            with st.chat_message("human"):
                st.write(content)
        elif message_type == "tool" or message.get("role") == "tool":
            with st.chat_message("tool"):
                tool_name = message.get("tool_name")
                if tool_name:
                    st.markdown(f"**{tool_name}**")
                st.write(content)
        else:
            with st.chat_message("ai"):
                st.write(content)


def _tool_result_to_text(result: Any) -> str:
    from mcp.types import TextContent

    if getattr(result, "structuredContent", None):
        return json.dumps(result.structuredContent, ensure_ascii=False, indent=2)

    lines: List[str] = []
    for item in getattr(result, "content", []) or []:
        if isinstance(item, TextContent):
            lines.append(item.text)
        else:
            try:
                lines.append(json.dumps(item.model_dump(), ensure_ascii=False, indent=2))
            except Exception:  # pragma: no cover - best effort serialisation
                lines.append(str(item))

    return "\n\n".join(lines) if lines else ""


async def _handle_chat(prompt: str) -> None:
    st.session_state.messages.append({"type": "human", "role": "user", "content": prompt})

    with st.chat_message("human"):
        st.write(prompt)

    mcp_client = await _get_mcp_client()
    openai_client: AsyncOpenAI = st.session_state.openai_client

    assistant_container = st.chat_message("ai")
    assistant_placeholder = assistant_container.empty()

    openai_messages = _as_openai_messages(st.session_state.messages)

    response_id: Optional[str] = None
    assistant_message = {"type": "ai", "role": "assistant", "content": ""}
    pending_tool_calls: Dict[str, Dict[str, Any]] = defaultdict(dict)
    queued_tool_outputs: List[Dict[str, str]] = []

    async def submit_pending_outputs() -> None:
        nonlocal queued_tool_outputs, response_id
        if response_id and queued_tool_outputs:
            await openai_client.responses.submit_tool_outputs(
                response_id=response_id,
                tool_outputs=queued_tool_outputs,
            )
            queued_tool_outputs = []

    try:
        async with openai_client.responses.stream(
            model=OPENAI_MODEL,
            messages=openai_messages,
            tools=[{"type": "mcp", "server_name": "mcp-sklearn"}],
        ) as stream:
            initial_response = getattr(stream, "response", None)
            if initial_response and not response_id:
                response_id = getattr(initial_response, "id", None) or (initial_response or {}).get("id")
                await submit_pending_outputs()

            async for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "response.created":
                    response = getattr(event, "response", None)
                    response_id = getattr(response, "id", None) or (response or {}).get("id")
                    await submit_pending_outputs()
                elif event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if isinstance(delta, str):
                        text = delta
                    else:
                        text = (delta or {}).get("text") or (delta or {}).get("content") or ""
                    if text:
                        assistant_message["content"] += text
                        assistant_placeholder.markdown(assistant_message["content"])
                elif event_type in {"response.tool_call.delta", "response.tool_call.completed"}:
                    payload: Dict[str, Any]
                    if event_type == "response.tool_call.delta":
                        payload = getattr(event, "delta", {}) or {}
                    else:
                        payload = (
                            getattr(event, "tool_call", None)
                            or getattr(event, "data", None)
                            or getattr(event, "delta", None)
                            or {}
                        )

                    call_id = payload.get("id")
                    if not call_id:
                        continue

                    call_state = pending_tool_calls[call_id]

                    if payload.get("name"):
                        call_state["name"] = payload["name"]

                    if payload.get("arguments"):
                        call_state.setdefault("arguments", "")
                        call_state["arguments"] += payload["arguments"]

                    status = payload.get("status") or payload.get("state")
                    if status == "completed" or event_type == "response.tool_call.completed":
                        tool_name = call_state.get("name")
                        arguments_text = call_state.get("arguments", "")

                        try:
                            tool_arguments = json.loads(arguments_text) if arguments_text else {}
                        except json.JSONDecodeError:
                            tool_arguments = {}

                        tool_result = await mcp_client.call_tool(tool_name, tool_arguments or None)
                        tool_output_text = _tool_result_to_text(tool_result)

                        tool_message = {
                            "type": "tool",
                            "role": "tool",
                            "tool_call_id": call_id,
                            "tool_name": tool_name,
                            "content": tool_output_text,
                        }
                        st.session_state.messages.append(tool_message)

                        with st.chat_message("tool"):
                            if tool_name:
                                st.markdown(f"**{tool_name}**")
                            st.write(tool_output_text)

                        if tool_output_text is not None:
                            queued_tool_outputs.append(
                                {
                                    "tool_call_id": call_id,
                                    "output": tool_output_text,
                                }
                            )
                            await submit_pending_outputs()

                        pending_tool_calls.pop(call_id, None)

            await stream.get_final_response()
    except Exception as exc:  # pragma: no cover - handled gracefully in UI
        assistant_placeholder.error(f"Error: {exc}")
        return

    if assistant_message["content"]:
        assistant_placeholder.markdown(assistant_message["content"])
        st.session_state.messages.append(assistant_message)


async def main() -> None:
    st.title("OpenAI chat with MCP tools")

    _init_state()
    _render_history(st.session_state.messages)

    prompt = st.chat_input()
    if prompt:
        await _handle_chat(prompt)


asyncio.run(main())
