from openai import OpenAI

class Agent:
    '''
    Abstract base class for all agents.

    Member variables:
        model (str): The model to use for the chat.
        prompt (str): The prompt to use for the chat.
        API_KEY (str): The API key to use for the chat.
        URL (str): The URL to use for the chat.

    Member functions:
        chat(input) -> response: Chat with the model using the input.
        gather_prompt(**kwargs): Gather the prompt for the chat.
    '''

    def __init__(self):
        self.model = None
        self.prompt = None
        self.API_KEY = None
        self.URL = None

    def chat(self, input):
        pass
    
    def gather_prompt(self, **kwargs):
        pass