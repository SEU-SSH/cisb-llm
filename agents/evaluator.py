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

        self.prompt = """You are an software security expert, evaluate and check the result of bug report analysis. 
        \nThe result consists of the longer [Reasoning Process] and the shorter [Generated Summary].
        \nYou need to reflect the [Reasoning Process] then determine whether CISB exists.
        \nThen answer the following questions with [yes/no]: 
        \n1. Does the report include source code? If no, terminate early.
        \n2. Does the given source code conform to his intention? If no, terminate early.
        \n3. Is the issue an actually bug? If no, it is not a bug.
        \n4. Caused by the conflict between user expectation and compiler optimization assumption? If no, it is a programming error.
        \n5. Does the bug have security implications in the context? If no, it is a compiler bug. If yes, it is a CISB.
        \nAfter answering the above questions, state whether this bug report reflects a CISB.
        \nFinal conclusion: [CISB / Not a CISB / Inconclusive due to early termination]
        """

        
    def chat(self, input):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(input)},
        ],
            max_tokens=2048,
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