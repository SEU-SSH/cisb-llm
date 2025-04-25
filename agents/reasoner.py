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
                'task': 'Your task is to analyse a bug report excerpt from a platform like GCC Bugzilla, determine whether the code contains [CISB].',
                # 'definition': '\n[CISB Definition]\n If the compiler\'s optimization induced a security-related bug in the code, then it is CISB.',
                'description': '\n[Bug Report Structure]\n The report will contain bug id, title, digested description and code logical blocks, formed as a json.',
                'requirement': '\n[Requirement 1]\n Please be careful not to overthink, nor do you need to suggest anything.'
            },
            'CoT': {
                'beginning': 'Let us think step by step.',
                #'draw problem desc': 'Firstly, you need to rephrase the situation described by the reporter as a standardized expression in the computer industry, summarizing its issues within 100 words. If the amount of information in the first comment is too low or the content is confusing, end the inference directly and report the exception.',
                'code location': 'First, based on the differences in user descriptions, locate key variables or function calls in the code blocks, trace them according to call chain. Reason about the approximate location which caused the expectation and reality differing.',
                'compiler behavior': 'Then, focus on the located code block and analyse possible behavior of the compiler. For example, whether the compiler has optimizations, what platform it is applied to, and what version it is.',
                'problem analysis': 'Summary if there is conflict between user expectations in that block and assumption of compiler optimization it makes. ',
                'gap analysis': 'If the reported function failure is truly caused by the conflict, leading to the reported bug and it may have security implications(such as check removed, endless loop, etc.), then it is a CISB.',
                'primary label': 'After analyzing the problem, proclaim if CISB exists.',
                'early termination': 'If the report lacks enough source code, please end the inference directly and report the exception.',
                'emphasis': '\n[Requirement 2]\n Remember we do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.',
                # 'reduce hallucination': '\n[Requirement 3]\n User\'s code is not necessarily valid according to language standards, nor his expectation. So Your reasoning do not need to rely on his expectations.'
                #'summarize and suggest': 'In the end, summarize the information and effectiveness provided by the bug report in one to two sentences, and point out the best practices.'
            }
        }

    def gather_prompt(self, **kwargs):
        self.prompt = """You are an expert in the field of software and system security.
        \nYour task is to analyse a bug report excerpt from a platform like GCC Bugzilla, determine whether the code contains [CISB].
        \n[Bug Report Structure]: The report will contain bug id, title, digested description and code logical blocks, formed as a json.
        \n[Requirement 1]: Please be careful not to overthink, nor do you need to suggest anything.
        \n[Requirement 2]: If the report lacks enough source code, please end the inference directly and report the exception.
        \n[Requirement 3]: Remember we do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.
        \nLet us reason about it step by step.
        \n[Step 1]: First you need to inspect if the given code conforms to what he issues. If no, terminate early.
        \n[Step 2]: Based on the differences in user descriptions, locate key variables or function calls in the code blocks, trace them according to call chain. Reason about the approximate location which caused the expectation and reality differing.
        \n[Step 3]: Focus on the located code block and analyse possible behavior of the compiler. For example, whether the compiler has optimizations, what platform it is applied to, and what version it is.
        \n[Step 4]: Summary if there is conflict between user expectations on the functionality of that block and assumption of compiler optimization it makes. 
        \n[Step 5]: Judge if the reported function failure is truly caused by the conflict, leading to the reported bug and it may have security implications(such as check removed, endless loop, etc.).
        \nAfter reasoning, answer the following questions with [yes/no] and one sentence explanation:
        \n1. Does the report include source code?
        \n2. Does the given source code conform to his intention? 
        \n3. Is the issue an actual bug in the code? 
        \n4. Caused by the conflict between user expectation and assumption compiler made to do optimization? 
        \n5. Does the bug have security implications in the context?
        \nIf the questions are all [yes], then it is a CISB.
        """
        # for key in kwargs:
        #     for k in self.template[key]:
        #         self.prompt += self.template[key][k] + '\n'
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
            max_tokens=4096,
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
            max_tokens=4096,
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