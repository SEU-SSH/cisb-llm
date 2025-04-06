from openai import OpenAI
from digestor import Digestor
from reasoner import Reasoner
from evaluator import Evaluator
from helper import Helper
import json


class Wrapper:

    def __init__(self, dmodel, rmodel, prompt, API_KEY, URL):
        self.digestor = Digestor(dmodel, prompt, API_KEY, URL)
        self.reasoner = Reasoner(rmodel, prompt, API_KEY, URL)
        self.evalutor = Evaluator(dmodel, prompt, API_KEY, URL)
        

    def gather_prompt(self, **kwargs):
        self.digestor.gather_prompt()
        self.reasoner.ZS_RO()
        self.evalutor.gather_prompt()

    def get_analysis(self, report):
        #self.digestor.gather_prompt()
        digest = self.digestor.chat(report)
        #print(digest.choices[0].message.content)
        #self.reasoner.ZS_RO()
        response = self.reasoner.chatZS(json.loads(digest.choices[0].message.content))
        return response
    
    def get_evaluation(self, report):
        response = self.evalutor.chat(report)
        return response

    def chat(self, id):
        self.gather_prompt()
        report = Helper().read_bug_report(id)
        analysis = self.get_analysis(report)
        Helper().generate_analysis_report(report, analysis)
        evaluation = self.get_evaluation(analysis)
        Helper().generate_evaluation(id, evaluation)


if __name__ == '__main__':
    dmodel = ''
    rmodel = ''
    url = ''
    API_KEY = ''

    chater = Wrapper(dmodel, rmodel, None, API_KEY, url)
    chater.chat()