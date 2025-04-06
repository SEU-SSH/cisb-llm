from agent import Agent
from openai import OpenAI
from helper import Helper

class Digestor(Agent):
    '''
    Digestor agent for creating a bug report digest.

    Member variables:
        model (str): The model to use for summary, should be a common chatting model.
        prompt (str): The prompt to use for the chat.
        API_KEY (str): The API key to use for the chat.
        URL (str): The URL to use for the chat.
    '''

    def __init__(self, model, prompt, API_KEY, URL):
        self.model = model
        self.prompt = prompt
        self.API_KEY = API_KEY
        self.URL = URL

    def chat(self, input):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(input)},
        ],
            max_tokens=1024,
            temperature=0.7,
            response_format={'type': 'json_object'},
            stream=False
        )

        print("Digest finished.")
        return response
    
    def gather_prompt(self, **kwargs):
        self.prompt = 'You are an expert bug report extraction assistant. Analyze the following bug report and extract key information in JSON format.' \
        'The report will contain bug id, summary, status, first comment information and some with attachments, formed as a json.' \
        'Output should include following information, constructed as a json: \n{'\
        '\n\t[id]: The bug id of the report.' \
        '\n\t[title]: The title of the report, stored as-is.' \
        '\n\t[description]: The refined description of the report content. Rephrase reporter\'s description as a standardized expression in the computer science within 100 words. Do not make any inference.' \
        '\n\t[code]: The code snippet provided in the report or the attachment, stored as-is.\n}' \
        
    def test(self, bug_id):
        self.gather_prompt()
        report = Helper().read_bug_report(bug_id)
        response = self.chat(report)
        # with open(f"{bug_id}_digest.json", "w", encoding="utf-8") as f:
        #     f.write(response.choices[0].message.content)
        # return
        Helper().generate_digest(report, response)

if __name__ == '__main__':
    model = ''
    url = ''
    api_key = ''


    demo = Digestor(model, None, api_key, url)
    # demo.gather_prompt()
    # print(demo.prompt)
    # demo.test()