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

    def __init__(self, model, prompt, API_KEY, URL, platform='bugzilla'):
        self.model = model
        self.prompt = prompt
        self.API_KEY = API_KEY
        self.URL = URL
        self.shots = []
        self.platform = platform

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
                'gap analysis': 'If the reported function failure is truly caused by the conflict, leading to reported bug and it may have security implications(such as check removed, endless loop, etc.), then it is a CISB.',
                'primary label': 'After analyzing the problem, proclaim if CISB exists.',
                'early termination': 'If the report lacks enough source code, please end the inference directly and report the exception.',
                'emphasis': '\n[Requirement 2]\n Remember we do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.',
                # 'reduce hallucination': '\n[Requirement 3]\n User\'s code is not necessarily valid according to language standards, nor his expectation. So Your reasoning do not need to rely on his expectations.'
                #'summarize and suggest': 'In the end, summarize the information and effectiveness provided by the bug report in one to two sentences, and point out the best practices.'
            }
        }

    def gather_prompt(self, **kwargs):
        if self.platform == 'bugzilla':
            self.prompt = """You are an expert in the field of software and system security.
            \nYour task is to analyse a bug report excerpt from a platform like GCC Bugzilla, determine whether the code contains [CISB].
            \n\n[Bug Report Structure]: The report contains bug id, title, digested description, code logical blocks and review from Bugzilla developers, formed as json.
            \n[Requirement 1]: Do not overthink or recommend anything.
            \n[Requirement 2]: Your reason must base on source code. If lacking enough source code, terminate the inference directly and raise exception.
            \n[Requirement 3]: Do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.
            \n[Requirement 4]: Concepts you MUST distinguish: \n<Default Behavior>: compilers decide it is appropriate to perform certain default behaviors or make default assumptions. Such as inlining, type promotion, assuming function must return, etc.\n<Programming Error>: Violations explicitly marked as invalid by the language specification (e.g., constraint violations, reserved keyword misuse). programming error is not CISB.\n<Undefined Behavior> (UB): Behavior where the standard imposes no requirements. UB is not necessarily programming error. Do not assume that all UB cases indicate programming error. When UB in the code has security implications even without compiler process, it is programming error (e.g., using negative index).
            \n\nLet us reason about it step by step.
            \n[Step 1]: First check if the given code conforms to what he issues. If no, terminate early.
            \n[Step 2]: Based on the differences in user descriptions, locate key variables or function calls in the code blocks, trace them through call chains. Reason about the approximate location which caused the differences. If you cannot locate a specific source code, terminate early and report the exception.
            \n[Step 3]: Focus on the located code block, analyse probable optimization or default behavior done by compiler on the block. Do not rush to a conclusion.
            \n[Step 4]: Summary the behavior expected by user on the located code and the actual after compilation, whether it differs. You may refer to the developer review. Note that if review specifies the bug is caused by external factors such as hardware, environment or configuration, then it is not CISB.
            \n[Step 5]: Judge if the bug is caused by the differences in Step 4, and whether may have security implications in the context. No matter what the root cause is.
            \n\nAfter reasoning, you should conclude your reasoning content, then output the analysis results in below structure.
            \n\n**Title**: brief conclusion of the report.
            \n**Issue**: how the program observable behavior differs from user expectation.
            \n**Tag**: classify the report within a phrase. such as code enhance, config fix, etc.
            \n**Purpose**: what the report intend to reveal or suggest.
            \n---\n
            ### Step-by-Step Analysis:
            \n1. **Key Variables/Functionality**: where the issue emerges on source code.
            \n2. **Compiler Behavior**: whether and what the optimization, default behavior on specific code.
            \n3. **Pre/Post Compilation**: the difference before and after compiler process on code.
            \n4. **Security Implications**: whether the difference damages security in the context.
            \n---\n
            \nAnswer the following questions with [yes/no] and one sentence explanation:
            \n1. Did compiler accept the code and compile it successfully?
            \n2. Is the issuer reporting a runtime bug, and provoked during optimization or default behavior?
            \n3. Without optimization or default behavior, will the difference in Step 4 disappear?
            \n4. Did the program observable behavior change after optimization or default behavior during execution?
            \n5. Does this change have direct or indirect security implications in the context?
            \nDirect implications such as endless loop/program hang, crash, memory corruption, etc. Indirect implications such as data leak, control flow diversion, check removed/bypassed, and more covert like side channel, speculative execution, etc.
            \n\n**CISB Status**: If answers are all [yes], then it is a CISB.
            """
        elif self.platform == 'kernel':
            self.prompt = """
            You are an expert in the field of software and system security.
            \nYour task is to analyse a commit from Linux kernel, determine whether the patch reveals a potential [CISB].
            \n\n[Bug Report Structure]: The report contains commit id, title, digested description, patch context and diff code logical blocks, formed as json.
            \n[Requirement 1]: Do not overthink or recommend anything.
            \n[Requirement 2]: Your reason must base on source code. If lacking enough source code, terminate the inference directly and raise exception.
            \n[Requirement 3]: Do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.
            \n[Requirement 4]: Concepts you MUST distinguish: \n<Default Behavior>: compilers decide it is appropriate to perform certain default behaviors or make default assumptions. Such as inlining, type promotion, assuming function must return, etc.\n<Programming Error>: Violations explicitly marked as invalid by the language specification (e.g., constraint violations, reserved keyword misuse). \n<Undefined Behavior> (UB): Behavior where the standard imposes no requirements. UB is not necessarily programming error because in sometimes it is required in certain environment, such as data race in kernel. Do not assume that all UB cases indicate programming error.
            \n\nLet us reason about it step by step.
            \n[Step 1]: Locate key variables or function calls in the code blocks, trace them through call chains in the patch context. Then summarize their functionality. If you cannot locate a specific source code, terminate early and report the exception.
            \n[Step 2]: According to the issue in message, analyse the probable optimization or default behavior done by compiler on the located code block. Do not rush to a conclusion.
            \n[Step 3]: Contrast the previous functionality and the actual after compilation, whether it differs after the compiler process in Step 2. It is not about patch difference but compilation process.
            \n[Step 4]: Judge if the issue is caused by the differences in Step 3, and whether may have security implications in kernel context. No matter what the root cause is.
            \n\nAfter reasoning, you should conclude your reasoning content, then output the analysis results in below structure.
            \n\n**Title**: brief conclusion of the commit.
            \n**Issue**: how the program observable behavior differs from expectation.
            \n**Tag**: classify the commit within a phrase. such as code enhance, config fix, etc.
            \n**Purpose**: what the commit intend to edit or revise.
            \n---\n
            ### Step-by-Step Analysis:
            \n1. **Key Variables/Functionality**: where the issue emerges on source code.
            \n2. **Compiler Behavior**: whether and what the optimization, default behavior on specific code.
            \n3. **Pre/Post Compilation**: the difference before and after compiler process on code, not patch diff.
            \n4. **Security Implications**: whether the difference damages security in kernel context.
            \n---\n
            \nAnswer the following questions with [yes/no] and one sentence explanation:
            \n1. Did compiler accept the kernel code and compile it successfully?
            \n2. Is the issuer reporting a runtime bug, where previous code semantic assumption was damaged during optimization or default behavior?
            \n3. Without optimization or default behavior, will the difference in Step 3 disappear?
            \n4. Did the program observable behavior change after optimization or default behavior during execution?
            \n5. Does this change have direct or indirect security implications in the context?
            \nDirect implications such as endless loop/program hang, crash, memory corruption, etc. Indirect implications such as data leak, control flow diversion, check removed/bypassed, and more covert like side channel, speculative execution, etc.
            \n\n**CISB Status**: If answers are all [yes], then it is a CISB.
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

    def ZS_RO(self, **kwargs):
        self.gather_prompt()

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
        # print("reasoning...", self.model)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(report)},
        ],
            # max_tokens=4096,
            temperature=1.0,
            stream=False
        )

        # print(response.choices[0].message.content)
        print("Analysis finished.")
        return response
    
    def chatZS_stream(self, report):
        client = OpenAI(api_key=self.API_KEY, base_url=self.URL)
        # print("thinking...", self.model)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(report)},
        ],
            extra_body={"enable_thinking": True},
            temperature=1.0,
            stream=True
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
            model="deepseek-reasoner",
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
        report = Helper().read_digest(bug_id if self.platform == 'bugzilla' else bug_id[:10])
        if self.model != "":
            response = self.chatZS(report)
            Helper().generate_analysis_report(report, response)
        else:
            response = self.chatZS_stream(report)
            Helper().generate_analysis_report_stream(report, response)


if __name__ == "__main__":
    #print(report['id'])
    # generate_analysis_report(report)
    model = ""
    url = ""
    api_key = ""

    test = Reasoner(model, None, api_key, url, platform='kernel')
    test.gather_prompt()
    test.test('')
    # test= Reasoner(model, None, api_key, url)
    # test.gather_prompt()
    # print(test.prompt)