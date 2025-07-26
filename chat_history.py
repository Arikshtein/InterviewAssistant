from enum import Enum

class MESSAGE_TYPE(Enum):
    REALTIME = 'realtime'
    FINAL = 'final'

class ROLE(Enum):
    USER = 'user'
    ASSISTANT = 'assistant'

class ChatHistory:
    def __init__(self):
        self._list = []
        self._last_message_id = {
            "user": {
                "final": -1,
                "realtime": -1
            },
            "assistant": {
                "final": -1,
                "realtime": -1
            }
        }

    def get_by_id(self, id:int):
        return self._list[id]

    def clear(self):
        self._list = []
        self._last_message_id = {
            "user": {
                "final": -1,
                "realtime": -1
            },
            "assistant": {
                "final": -1,
                "realtime": -1
            }
        }

    def put(self, role:ROLE, type:MESSAGE_TYPE, content:str):
        if self._last_message_id[role.value]['realtime'] == -1:
            self._list.append({"role": role.value, "transcription_type": type.value, "content": content})
            self._last_message_id[role.value]['realtime'] = len(self._list)-1
            return (self._last_message_id[role.value]['realtime'], 'new')
        
        if type.value == 'final':
            self._list[self._last_message_id[role.value]['realtime']]['content'] = content
            self._list[self._last_message_id[role.value]['realtime']]['transcription_type'] = 'final'
            self._last_message_id[role.value]['final'] = self._last_message_id[role.value]['realtime']
            self._list.append({"role": role.value, "transcription_type": "realtime", "content": ""})
            self._last_message_id[role.value]['realtime'] = -1
            return (self._last_message_id[role.value]['final'], 'existing')
        else:
            self._list[self._last_message_id[role.value]['realtime']]['content'] = content
            return (self._last_message_id[role.value]['realtime'], 'existing')
        

    def as_list(self, realtime=True, until_latest_user_final=False):
        if realtime:
            return self._list
        if until_latest_user_final:
            return self._list[:self._last_message_id['user']['final']]
        else:
            return self._list[:max(self._last_message_id['user']['realtime'], self._last_message_id['assistant']['realtime'])]