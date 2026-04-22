import json

from openai import OpenAI


class Agent:
    """
    Abstract base class for all agents.

    Member variables:
        model (str): The model to use for the chat.
        prompt (str): The prompt to use for the chat.
        API_KEY (str): The API key to use for the chat.
        URL (str): The URL to use for the chat.
        platform (str): The platform to use for the chat, e.g., 'bugzilla' or 'kernel'.

    Member functions:
        chat(input) -> response: Chat with the model using the input.
        gather_prompt(**kwargs): Gather the prompt for the chat.
    """

    def __init__(self):
        self.model = None
        self.prompt = None
        self.API_KEY = None
        self.URL = None
        self.platform = None

    def chat(self, input):
        pass

    def gather_prompt(self, **kwargs):
        pass

    def run(self, state):
        raise NotImplementedError("run() is only implemented for agentic agents.")

    def build_client(self):
        return OpenAI(api_key=self.API_KEY, base_url=self.URL)

    @staticmethod
    def extract_text(response):
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text

        if hasattr(response, "choices") and response.choices:
            message = getattr(response.choices[0], "message", None)
            if message is not None and getattr(message, "content", None):
                return message.content

        output = getattr(response, "output", None)
        if output:
            chunks = []
            for item in output:
                contents = (
                    item.get("content", [])
                    if isinstance(item, dict)
                    else getattr(item, "content", [])
                )
                for content in contents:
                    text = (
                        content.get("text")
                        if isinstance(content, dict)
                        else getattr(content, "text", None)
                    )
                    if text:
                        chunks.append(text)
            if chunks:
                return "".join(chunks)

        return ""

    @staticmethod
    def extract_json_payload(text):
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty response while expecting JSON payload.")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])

        raise ValueError("No valid JSON object found in model response.")

    def complete_chat(
        self,
        messages,
        json_mode=False,
        temperature=0.2,
        max_tokens=4096,
        extra_body=None,
    ):
        client = self.build_client()
        last_error = None
        if json_mode:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                return self.extract_text(response)
            except Exception as exc:
                # Fall back to plain text generation and parse the JSON payload.
                last_error = exc

        try:
            if hasattr(client, "responses"):
                response = client.responses.create(
                    model=self.model,
                    input=messages,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    extra_body=extra_body,
                    stream=False,
                )
                return self.extract_text(response)

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self.extract_text(response)
        except Exception as exc:
            if last_error is not None:
                raise last_error
            raise exc
