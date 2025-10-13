import asyncio
import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_SCRIPT = Path(__file__).resolve().parents[1] / "server" / "server.py"


@asynccontextmanager
async def connect_to_mcp_server() -> AsyncIterator[ClientSession]:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"MCP server script not found: {SERVER_SCRIPT}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(SERVER_SCRIPT.parent),
        env={"PYTHONUNBUFFERED": "1"},
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        session = ClientSession(read_stream, write_stream)
        await session.initialize()
        try:
            yield session
        finally:
            pass


def _format_tool_result(result: types.CallToolResult) -> str:
    parts: List[str] = []

    for item in result.content:
        data = item.model_dump()
        if data.get("type") == "text":
            text = data.get("text", "")
            if text:
                parts.append(text)
        else:
            parts.append(json.dumps(data, ensure_ascii=False, indent=2))

    if result.structuredContent is not None:
        parts.append(json.dumps(result.structuredContent, ensure_ascii=False, indent=2))

    formatted = "\n\n".join(part for part in parts if part)
    return formatted or "(no output)"


async def _load_tool_config(session: ClientSession) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    tools_result = await session.list_tools()
    tool_specs: List[Dict[str, Any]] = []
    tool_info: List[Dict[str, str]] = []

    for tool in tools_result.tools:
        parameters: Dict[str, Any] = tool.inputSchema or {
            "type": "object",
            "properties": {},
        }

        tool_specs.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": parameters,
                },
            }
        )

        tool_info.append(
            {
                "name": tool.name,
                "description": tool.description or "",
            }
        )

    return tool_specs, tool_info


def _parse_tool_call(tool_call: Any) -> Tuple[str, Dict[str, Any], str | None]:
    name = getattr(tool_call, "name", None) or tool_call.get("name")  # type: ignore[arg-type]
    args = getattr(tool_call, "args", None) or tool_call.get("args", {})  # type: ignore[arg-type]
    call_id = getattr(tool_call, "id", None) or tool_call.get("id")  # type: ignore[arg-type]

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"input": args}

    if not isinstance(args, dict):
        raise TypeError(f"Tool arguments must be a dictionary, received: {type(args)!r}")

    if not name:
        raise ValueError("Tool call did not include a tool name.")

    return name, args, call_id


async def _ensure_tool_cache() -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    cache = st.session_state.get("tool_cache")
    if cache is not None:
        return cache["specs"], cache["info"]

    async with connect_to_mcp_server() as session:
        tool_specs, tool_info = await _load_tool_config(session)

    st.session_state.tool_cache = {"specs": tool_specs, "info": tool_info}
    return tool_specs, tool_info


async def main() -> None:
    st.set_page_config(page_title="MCP CSV Analyst")
    st.title("OpenAI chat with MCP tools")

    try:
        tool_specs, tool_info = await _ensure_tool_cache()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to connect to MCP server: {exc}")
        return

    with st.sidebar:
        st.subheader("Available MCP tools")
        for item in tool_info:
            st.markdown(f"**{item['name']}**: {item['description'] or 'No description'}")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message.type):
            st.write(message.content)

    if prompt := st.chat_input("Ask about the available datasets or analysis"):
        human_message = HumanMessage(prompt)
        st.session_state.messages.append(human_message)

        with st.chat_message("human"):
            st.write(prompt)

        chat_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        tool_enabled_model = chat_model.bind_tools(tool_specs)

        try:
            async with connect_to_mcp_server() as session:
                while True:
                    ai_response: AIMessage = await tool_enabled_model.ainvoke(st.session_state.messages)
                    st.session_state.messages.append(ai_response)

                    with st.chat_message("ai"):
                        if ai_response.content:
                            st.write(ai_response.content)
                        if ai_response.tool_calls:
                            tool_names = ", ".join(
                                getattr(call, "name", getattr(call, "tool_name", "tool")) or "tool"
                                for call in ai_response.tool_calls
                            )
                            st.caption(f"Invoking tool(s): {tool_names}")

                    if not ai_response.tool_calls:
                        break

                    for tool_call in ai_response.tool_calls:
                        name, args, call_id = _parse_tool_call(tool_call)
                        with st.spinner(f"Running tool '{name}'..."):
                            try:
                                result = await session.call_tool(name, args)
                            except Exception as exc:  # noqa: BLE001
                                error_message = f"Error calling {name}: {exc}"
                                st.session_state.messages.append(
                                    ToolMessage(content=error_message, tool_call_id=call_id or "", name=name)
                                )
                                with st.chat_message("tool"):
                                    st.error(error_message)
                                continue

                        output_text = _format_tool_result(result)

                        st.session_state.messages.append(
                            ToolMessage(content=output_text, tool_call_id=call_id or "", name=name)
                        )

                        with st.chat_message("tool"):
                            if result.isError:
                                st.error(output_text)
                            else:
                                st.markdown(f"**{name}** result:")
                                st.write(output_text)
        except FileNotFoundError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Unexpected error while communicating with MCP server: {exc}")


asyncio.run(main())
