import time
import requests
from enum import Enum
import json
from threading import Event
from typing import Generator

SYSTEM_PROMPT = """
You are roleplaying as a coach for the job applicant being interviewed for a professional position. 
Your goal is to provide feedback on how the interview is going based on the provided conversation transcript. 
The feedback should include potential points of improvements 
"""

from abc import ABC, abstractmethod

# Abstract class from where each LLM provider API will be interited
class _LLMAPI:
    @abstractmethod
    def __init__(self):
        self.baseurl:str = None
        self.list_models_endpoint: str = None
        self.header:dict = {"Content-Type": "application/json"}
        self.model:str = None
        self.system_prompt = SYSTEM_PROMPT

    @abstractmethod
    def authenticate(self) -> None:
        raise NotImplementedError

    def set_system_prompt(self,new_prompt) -> None:
        self.system_prompt = new_prompt

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def select_model(self, model: str) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def chat(self, chat_history) -> Generator[str, None, None]:
        raise NotImplementedError


class OpenAIAPI(_LLMAPI):
    def __init__(self):
        super().__init__()
        self.baseurl = "https://api.openai.com/v1"
        self.list_models_endpoint: str = 'models'
        self.chat_endpoint: str = 'chat/completions'

    def authenticate(self, apikey_filepath: str = 'apikey') -> None:
        with open(apikey_filepath, 'r') as k:
            self.header["Authorization"] = "Bearer " + k.read()

    def list_models(self) -> list[str]:
        if not(self.header.get("Authorization")):
            raise Exception("Not authenticated")
        models_response = requests.get(self.baseurl + '/' + self.list_models_endpoint, headers=self.header)
        models_response.raise_for_status()

        all_models = json.loads(models_response.content)
        all_model_names = [x['id'] for x in all_models['data']]
        return all_model_names
        

    def select_model(self, model: str = "gpt-4.1-nano") -> None:
        if not(self.header.get("Authorization")):
            raise Exception("Not authenticated")
        models_response = requests.get(self.baseurl + '/' + self.list_models_endpoint, headers=self.header)
        models_response.raise_for_status()

        all_models = json.loads(models_response.content)
        all_model_names = [x['id'] for x in all_models['data']]
        if model not in all_model_names:
            raise Exception("Selected model '" + model + "' not in: " + ', '.join(all_model_names))
        
        self.select_model = model

    def chat(self, chat_history, terminate: Event) -> Generator[str, None, None]:
        if not(self.header.get("Authorization")):
            raise Exception("Not authenticated")
        if not(self.select_model):
            raise Exception("Model not selected")

        with requests.post(
            self.baseurl + '/' + self.chat_endpoint, 
            headers=self.header,
            json={
                "model": self.select_model,
                "messages": [{"role": "system", "content": self.system_prompt}] + chat_history
            }
        ) as chat_response:
            chat_response.raise_for_status()
            
            response_json = json.loads(chat_response.content)
            yield response_json.get('choices', [{}])[0].get('message', {}).get('content', '')


class OllamaAPI(_LLMAPI):
    def __init__(self):
        super().__init__()
        self.baseurl = "http://localhost:11434/api"
        self.list_models_endpoint: str = 'tags'
        self.chat_endpoint: str = 'chat'

    def authenticate(self, **kwargs) -> None:
        return

    def list_models(self) -> list[str]:
        models_response = requests.get(self.baseurl + '/' + self.list_models_endpoint, headers=self.header)
        models_response.raise_for_status()
        all_models = json.loads(models_response.content)
        all_model_names = [x['name'] for x in all_models['models']]
        return all_model_names

    def select_model(self, model: str = 'deepseek:7b') -> None:
        models_response = requests.get(self.baseurl + '/' + self.list_models_endpoint, headers=self.header)
        models_response.raise_for_status()

        all_models = json.loads(models_response.content)
        all_model_names = [x['name'] for x in all_models['models']]
        if model not in all_model_names:
            raise Exception("Selected model '" + model + "' not in: " + ', '.join(all_model_names))
        
        self.select_model = model

    def chat(self, chat_history, terminate: Event) -> Generator[str, None, None]:
        _now_thinking: bool = False
        
        if not(self.select_model):
            raise Exception("Model not selected")
        
        # Used to terminate the generation of the 
        #   response if another one was requested
        terminate.set()
        time.sleep(0.1)
        terminate = Event()

        with requests.post(
            self.baseurl + '/' + self.chat_endpoint, 
            headers=self.header,
            json={
                "model": self.select_model,
                "messages": [{"role": "system", "content": self.system_prompt}] + chat_history
            },
            stream=True
        ) as chat_response:
            chat_response.raise_for_status()
            
            for line in chat_response.iter_lines():
                data = json.loads(line.decode("utf-8"))

                if (r'<think>' in data['message']['content']):
                    _now_thinking=True
                if not(_now_thinking):
                    yield(data['message']['content'])
                if r'</think>' in data['message']['content']:
                    _now_thinking=False
                
                if terminate.is_set():
                    break

class APIProvider(Enum):
    OLLAMA = 'ollama'
    OPENAI = 'openai'


def LLMFactory(provider: APIProvider) -> _LLMAPI:
    if provider == APIProvider.OPENAI:
        return OpenAIAPI()
    elif provider == APIProvider.OLLAMA:
        return OllamaAPI()
    elif type(provider) != APIProvider:
        raise Exception("Provide a valid APIProvider enum instance")
    else:
        raise NotImplementedError