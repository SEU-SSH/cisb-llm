from agent import Agent
from openai import OpenAI
from helper import Helper

class Reasoner(Agent):
    '''
    Constitution:
    1. Set up a role
    2. State the trouble
    3. Define the task
    4. Extra requirements
    5. CoT (optional)
    '''

    def __init__(self, model, prompt, API_KEY, URL):
        self.model = model
        self.prompt = prompt
        self.API_KEY = API_KEY
        self.URL = URL
        self.shots = []

        self.template = {
            'static': {
                'role': 'You are an expert in the field of software and system security.',
                'task': 'Your task is to analyse a bug report excerpt from a platform like GCC Bugzilla, determine whether compiler introduced a silent bug in the code.',
                'description': 'The report will contain bug id, title, digested description and code, formed as a json.',
                'requirement': 'Please be careful not to overthink, nor do you need to suggest anything.'
            },
            'CoT': {
                'beginning': 'Let us think step by step.',
                #'draw problem desc': 'Firstly, you need to rephrase the situation described by the reporter as a standardized expression in the computer industry, summarizing its issues within 100 words. If the amount of information in the first comment is too low or the content is confusing, end the inference directly and report the exception.',
                'user expecting behavior': 'First, You need to infer the intention based on the desciptions and code in the digest, and analyze the expection of the user.',
                'compiler behavior': 'Then, integrate the code and output results to obtain the actual behavior of the compiler. For example, whether the compiler has optimizations, what platform it is applied to, and what version it is.',
                'problem analysis': 'Summary the gap between expectations and reality based on the above information.',
                'tentative classification': 'After analyzing the problem, try to classify the bug report, explain the reasons for each point, judge if compiler introduced the bug.',
                'early termination': 'If you cannot draw a determinative conclusion, please end the inference directly and report the exception.'
                #'summarize and suggest': 'In the end, summarize the information and effectiveness provided by the bug report in one to two sentences, and point out the best practices.'
            }
        }

    def gather_prompt(self, **kwargs):
        self.prompt = ''
        for key in kwargs:
            for k in self.template[key]:
                self.prompt += self.template[key][k] + '\n'
        # return self.prompt
    
    def fetch_example(self, example_filename):
        with open(f'few_shot/examples/{example_filename}.md', 'r') as f:
            return f.read()
    
    def fetch_reasoning(self, reasoning_filename):
        with open(f'few_shot/reasoning/{reasoning_filename}.txt', 'r') as f:
            return f.read()

    def ZS_RO(self):
        self.gather_prompt(static = True, CoT = True)

        return self.prompt
    
    def FS_RO(self, **kwargs):
        self.gather_prompt(static = True, CoT = True)
        
        for key in kwargs:
            self.shots.append({"role": "user", "content": self.fetch_example(kwargs[key])})
            self.shots.append({"role": "assistant", "content": self.fetch_reasoning(kwargs[key])})
        # prompt += '\n[user]\n' + self.fetch_example(kwargs['example1']) + '\n[assistant]\n' + self.fetch_reasoning(kwargs['reasoning1'])
        # prompt += '\n[user]\n' + self.fetch_example(kwargs['example2']) + '\n[assistant]\n' + self.fetch_reasoning(kwargs['reasoning2'])

        return self.shots
    
    def chatZS(self, report):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)
        response = client.chat.completions.create(
            model="",
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(report)},
        ],
            max_tokens=1024,
            temperature=0.7,
            stream=False
        )

        # print(response.choices[0].message.content)
        print("Analysis finished.")
        return response

    def chatFS(self, report):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)

        messages = [{"role": "system", "content": self.prompt}]
        for shot in self.shots:
            messages.append(shot)
        messages.append({"role": "user", "content": str(report)})

        response = client.chat.completions.create(
            model="",
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            stream=False
        )

        # print(response.choices[0].message.content)
        print("Analysis finished.")
        return response

    def test(self, bug_id):
        #self.gather_prompt()
        report = Helper().read_digest(bug_id)
        response = self.chatZS(report)
        Helper().generate_analysis_report(report, response)


if __name__ == "__main__":

    model = ''
    url = ''
    api_key = ''

    test = Reasoner(model, None, api_key, url)
    test.gather_prompt()
    test.test()