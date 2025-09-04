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
        platform (str): The platform to use for the chat, e.g., 'bugzilla' or 'kernel'.
    '''

    def __init__(self, model, prompt, API_KEY, URL, platform='bugzilla'):
        self.model = model
        self.prompt = prompt
        self.API_KEY = API_KEY
        self.URL = URL
        self.platform = platform

    def chat(self, input):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(input)},
        ],
            max_tokens=4096,
            temperature=1.0,
            response_format={'type': 'json_object'},
            stream=False
        )

        print("Digest finished.")
        return response
    
    def gather_prompt(self, **kwargs):
        if self.platform == 'bugzilla':
            self.prompt = """You are an expert bug report extraction assistant. Your task is to analyze the given bug report and extract key information in JSON format.
            \nThe report will contain bug id, summary, issue body and comments, wholly formed as a json. 
            \nRephrase reporter description in <issue body> as a standardized expression in the computer science field.
            \nFirst focus on the provided source code in <issue body>, try to divide it into some logical blocks, summarize their utilities.
            \nThen, associate the code with reporter description, conclude user's expectation and the differences from it according to the output.
            \nFinally, list the developer reviews as-is.
            \nOutput should include following information, constructed as a json: \n{
            [id]: The bug id of the report.
            [title]: The title of the report, stored as-is.
            [user expectation]: 
            [difference]: 
            [developer reviews]: ["<Issuer/Developer>: comment", "<Issuer/Developer>: comment", ...]
            [code block1]: {[functionality], [code]}
            [code block2]: {[functionality], [code]}
            ...\n}"""
        elif self.platform == 'kernel':
            self.prompt = """You are an expert git commit info extraction assistant. Your task is to analyze the given commit and extract key information in JSON format.
            \nThe report will contain bug id, year, message and patch context, wholly formed as a json. 
            \nRephrase developer description in message as a standardized expression in the computer science field. If the message contains source code, extract and append in the [patch context] naming 'message code'.
            \nFirst focus on the provided source code in patches, try to divide it into some logical blocks, summarize their patched code per file.
            \nThen, associate the code with developer description, conclude the previous issue, patching purpose and compiler behavior from it according to the output.
            \nOutput should include following information, constructed as a json: \n{
            [id]: The bug id of the report.
            [title]: The first sentence of the message, stored as-is.
            [previous issue]: 
            [patching purpose]: 
            [compiler behavior]: 
            [patch context]: extracted from patch context and message, stored per file, as-is.
            [message code]: code extracted from message, if any.
            [code block1]: {[before]}
            [code block2]: {[before]}
            ...\n}"""
        
    def test(self, bug_id):
        self.gather_prompt()
        # report = Helper().read_bug_report(bug_id, filename='bug_reports.json')
        report = Helper().read_commit(bug_id, filename='commits.json')
        response = self.chat(report)
        with open(f"{bug_id[:10] if self.platform == 'kernel' else bug_id}_digest.json", "w", encoding="utf-8") as f:
            f.write(response.choices[0].message.content)
        return
        #Helper().generate_digest(report, response)

if __name__ == '__main__':
    model = ""
    url = ""
    api_key = ""


    demo = Digestor(model, None, api_key, url, platform='kernel')
    # demo.gather_prompt(platform='kernel')
    # print(demo.prompt)
    demo.test('')