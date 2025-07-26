from textual.app import App
from textual.containers import VerticalScroll, Container
from textual.widgets import Static, Header, Footer
from textual.binding import Binding
from rich.panel import Panel
from rich.align import Align
from threading import Event
from rich.text import Text
from queue import Queue
import functools
import keyboard
from os import path

from chat_history import *
from gpt_request import LLMFactory, APIProvider, _LLMAPI

# import logging
# from textual.logging import TextualHandler
# logging.basicConfig(
#     level="INFO",
#     handlers=[TextualHandler()],
# )
# logger = logging.Logger("logger")

LLM_PROVIDER = APIProvider.OPENAI
LLM_MODEL = 'gpt-4.1-nano'

gpt_queue = Queue()
terminate_event = Event()

class ChatMessage(Static):
    def __init__(self, sender: ROLE, text: str, id: str, classes: str):
        super().__init__()
        self.sender = sender
        self.text = text
        self.id = id
        self.classes = classes

    def render(self):
        alignment = "right" if self.sender == ROLE.ASSISTANT.value else "left"
        return Align(
            Panel(Text(self.text, no_wrap=False, overflow="fold", justify=alignment)),
            align=alignment
        )
    
    def update(self, new_text: str):
        self.text = new_text
        self.refresh()

class ChatView(VerticalScroll):
    def on_mount(self):
        self.border_title = "Chat History"

    async def process_message(self, message_id: int, message_type: str):
        chat_message = self.app._chat_history.get_by_id(message_id)            

        if message_type == 'new':
            align = 'left' if chat_message['role'] == ROLE.USER.value else 'right'

            container = Container(classes = 'align_'+align)
            await self.mount(container)
            await container.mount(Static(chat_message['content'], classes='chat_message chat_message_' + align, id="msg"+str(message_id)))

            self.scroll_end(animate=False)
        else:
            existing_element = self.query_exactly_one("#msg"+str(message_id))
            existing_element.update(chat_message['content'])

class ChatApp(App):
    BINDINGS = [
        Binding(key="+", action="increase_gpt_window_width", description="Increase GPT container width"),
        Binding(key='-', action="decrease_gpt_window_width", description="Decrease GPT container width"),
        Binding(key="f7", action="generate_gpt_feedback", description="Generate Feedback"),
        Binding(key="f8", action="clear_chat", description="Clear the chat"),
        Binding(key="Ctrl +", action="zoom_in", description="Zoom In"),
        Binding(key="Ctrl -", action="zoom_out", description="Zoom Out"),
    ]
    CSS_PATH = "dom.tcss"

    def __init__(self, message_queue: Queue, **kwargs):
        super().__init__(**kwargs)
        self.message_queue = message_queue
        self._chat_history = ChatHistory()

    def action_increase_gpt_window_width(self):
        modify_gpt_window_width(self, increase=True)

    def action_decrease_gpt_window_width(self):
        modify_gpt_window_width(self, increase=False)

    def action_clear_chat(self):
        # logger.info("Chat history cleared")
        self._chat_history.clear()
        for wdgt in self.chat.children:
            wdgt.remove()

    def compose(self):
        self.header = Header(name="Interview Assist")   
        self.chat = ChatView(id="chatcontainer", name = "Chat History")
        self.footer = Footer(show_command_palette=True)
        self.gpt = VerticalScroll(Static("", id='gpt-content'), id='gpt')
        yield self.chat
        yield self.header
        yield self.gpt
        yield self.footer

    def on_mount(self):
        gptService = LLMFactory(LLM_PROVIDER)
        gptService.authenticate()
        gptService.select_model(LLM_MODEL)

        if path.isfile('systemprompt.txt'):
            with open('systemprompt.txt', 'r', encoding='utf-8') as spf:
                gptService.set_system_prompt(spf.read())

        keyboard.on_press_key('F7', functools.partial(generate_reply, gptService, self._chat_history))

        # Start polling queue every 100ms
        self.gpt.border_title = "GPT Feedback"
        self.set_interval(0.1, self.check_message_queue)
        self.set_interval(0.01, self.check_gpt_queue)

    async def check_message_queue(self):
        """Process all pending messages from the thread-safe queue."""
        if not self.message_queue.empty():
            chat_message = self.message_queue.get_nowait()
            message_id, message_type = self._chat_history.put(chat_message['role'], chat_message['transcription_type'], chat_message['content'])
            await self.chat.process_message(message_id, message_type)

    async def check_gpt_queue(self):
        global gpt_queue
        
        if not(gpt_queue.empty()):
            chunk = gpt_queue.get()
            object_to_update = self.query_exactly_one('#gpt-content')
            if chunk == '|||':
                object_to_update.update("")
            else:
                object_to_update.update(object_to_update.renderable + chunk)



def modify_gpt_window_width(app: ChatApp, increase: bool=False, increment: int = 5):
    delta = increment if increase==False else -increment
    elem = app.query_exactly_one("#chatcontainer")
    current_width = elem.styles.width.value
    if (current_width + delta <= 20) or (current_width + delta >= 80):
        return
    new_width = str(current_width + delta)+'%'
    elem.styles.width = new_width
    app.refresh()


def generate_reply(gptService: _LLMAPI, chat_history: ChatHistory, event=None):
    global gpt_queue, terminate_event

    gpt_queue.put("|||")
    chat_history_llm = chat_history.as_list(until_latest_user_final=True)
    if chat_history_llm:
        for z in gptService.chat(chat_history_llm, terminate_event):
            gpt_queue.put(z)