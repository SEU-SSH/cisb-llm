from agent import Agent
from openai import OpenAI
from helper import Helper

class Evaluator(Agent):

    '''
    Evaluator
    Utilize LLM to judge if the bug report is valid or not.
    Reflect the result in the analysis report.
    If bug exists, judge if the bug is secuity related.
    '''

    def __init__(self, model, prompt, API_KEY, URL):
        self.model = model
        self.prompt = prompt
        self.API_KEY = API_KEY
        self.URL = URL

    def gather_prompt(self, **kwargs):

        self.prompt = 'You are an software security expert, evaluate and conclude the result of bug report analysis.' \
        '\nThe result consists of the longer [Reasoning process] and the shorter [Generated summary].' \
        '\nYou need to reflect the [Reasoning process] then extract all the reasoning chains and list them clearly.' \
        '\nThen: ' \
        '\n1. Conclude the exact optimization behavior within 15 words.'\
        '\n2. State the security consequences within 15 words' \
        '\n3. Rephrase the eventual conclusion in one sentence within 15 words.' \
        '\nAccording to the reflection, you should re-evaulate the bug report analysis classification and label\'s validity.' \
        '\nIf compiler\'s behavior led to the bug, then consider if the bug is security related.' \
        '\nIf compiler\'s optimization is based on the No-UB assumption, then the generated code may also contain security implications.'

        
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
            # response_format={'type': 'json_object'},
            stream=False
        )

        print("Evaluation finished.")
        return response
    
    def test(self, bug_id):
        analysis = Helper().read_analysis(bug_id)
        response = self.chat(analysis)
        Helper().generate_evaluation(bug_id, response)


if __name__ == "__main__":
    model = ''
    url = ''
    api_key = ''

    evaluator = Evaluator(model, None, api_key, url)
    evaluator.gather_prompt()
    # print(evaluator.prompt)
    # evaluator.test()