from openai import OpenAI
from digestor import Digestor
from reasoner import Reasoner
from helper import Helper
from time import sleep
from os import system
import json
import dotenv
import os

class Wrapper:
    def __init__(
        self,
        dmodel,
        rmodel,
        prompt,
        API_KEY1,
        API_KEY2,
        URL1,
        URL2,
        platform="bugzilla",
    ):
        self.digestor = Digestor(dmodel, prompt, API_KEY1, URL1, platform)
        self.reasoner = Reasoner(rmodel, prompt, API_KEY2, URL2, platform)

    def gather_prompt(self, **kwargs):
        self.digestor.gather_prompt()
        self.reasoner.ZS_RO()
        # self.evalutor.gather_prompt()

    def get_analysis(self, report):
        # self.digestor.gather_prompt()
        digest = self.digestor.chat(report)
        # print(digest.output_text)
        # self.reasoner.ZS_RO()
        digest_text = Helper().extract_response_text(digest)
        if self.reasoner.model == "deepseek-reasoner":
            response = self.reasoner.chatZS(
                json.loads(digest_text)
            )
        else:
            response = self.reasoner.chatZS_stream(
                json.loads(digest_text)
            )
        return response

    # def get_evaluation(self, report):
    #     response = self.evalutor.chat(report)
    #     return response

    def chat(self, id):
        report = Helper().read_bug_report(id, filename="commits.json")
        analysis = self.get_analysis(report)
        if self.reasoner.model == "deepseek-reasoner":
            Helper().generate_analysis_report(report, analysis)
        else:
            Helper().generate_analysis_report_stream(report, analysis)
        # evaluation = self.get_evaluation(analysis)
        # Helper().generate_evaluation(id, evaluation)


if __name__ == "__main__":
    dotenv.load_dotenv()
    dmodel = os.getenv("DS_MODEL_NAME")
    # rmodel = ''
    rmodel = os.getenv("QWEN_MODEL_NAME")
    url1 = os.getenv("DS_API_URL")
    url2 = os.getenv("QWEN_API_URL")
    API_KEY1 = os.getenv("DS_API_KEY")
    API_KEY2 = os.getenv("QWEN_API_KEY")
    platform = "kernel"  # or 'kernel'

    # chater = Wrapper(dmodel, rmodel, None, API_KEY1, API_KEY1, url1, url1, platform)
    chater = Wrapper(dmodel, rmodel, None, API_KEY1, API_KEY2, url1, url2, platform)
    chater.gather_prompt()

    reports = Helper().read_ids("commits.txt")
    logs = open("errors.log", "w")
    errorIds = []
    if platform == "kernel":
        print([id[:10] for id in reports], len(reports))
    else:
        print([id for id in reports], len(reports))
    print("Using reasoning model: ", rmodel)
    confirm = input("No error? (y/n) ")
    if confirm.lower() != "y":
        print("Exiting...")
        exit()

    for report in reports:
        try:
            chater.chat(report.strip())
            sleep(30)  # Avoid rate limit, sleep for 30 seconds between requests
        except Exception as e:
            print(f"Error: {report} chating\n", e)
            errorIds.append(report.strip())

    logs.write("\n".join(errorIds))
    logs.close()
    print("All reports have been processed. Shutting down...")
    # system('shutdown -s -t 60')
