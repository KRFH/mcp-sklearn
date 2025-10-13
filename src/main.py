import asyncio

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


async def main():
    st.title("OpenAI chat with MCP tools")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    messages = st.session_state.messages

    for message in messages:
        with st.chat_message(message.type):
            st.write(message.content)

    if prompt := st.chat_input():
        with st.chat_message("human"):
            st.write(prompt)

        messages.append(HumanMessage(prompt))

        chat_model = ChatOpenAI(model="gpt-4o-mini")
        ai_response = await chat_model.ainvoke(messages)

        messages.append(ai_response)

        with st.chat_message("ai"):
            st.write(ai_response.content)


asyncio.run(main())
