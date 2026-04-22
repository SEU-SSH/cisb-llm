from openai import OpenAI
from digestor import Digestor
from reasoner import Reasoner
from agentic_kernel import AgenticKernelOrchestrator
from helper import Helper
from time import sleep
from os import system
import json
import os

try:
    import dotenv
except ImportError:  # pragma: no cover - optional dependency for CLI usage only.
    dotenv = None


def load_env_file(path):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"'", '"'}
            ):
                value = value[1:-1]
            os.environ.setdefault(key, value)


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
        mode="legacy",
        output_dir=None,
        cache_dir=None,
        cache_policy=None,
    ):
        self.platform = platform
        self.mode = mode
        self.digestor = Digestor(dmodel, prompt, API_KEY1, URL1, platform)
        self.reasoner = Reasoner(rmodel, prompt, API_KEY2, URL2, platform)
        self.agentic = None
        if platform == "kernel":
            self.agentic = AgenticKernelOrchestrator(
                dmodel,
                rmodel,
                API_KEY1,
                API_KEY2,
                URL1,
                URL2,
                output_dir=output_dir,
                cache_dir=cache_dir,
                cache_policy=cache_policy,
            )

    def gather_prompt(self, **kwargs):
        if self.mode == "agentic":
            return
        self.digestor.gather_prompt()
        self.reasoner.ZS_RO()
        # self.evalutor.gather_prompt()

    def get_analysis(self, report):
        if self.mode == "agentic":
            if self.platform != "kernel" or self.agentic is None:
                raise ValueError("Agentic mode is currently implemented for kernel only.")
            return self.agentic.run(report["id"], seed_report=report, persist=False)

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
        report = Helper().read_kernel_report(id, filename="commits.json")
        analysis = self.get_analysis(report)
        if self.mode == "agentic":
            self.agentic.persist(analysis)
            return analysis
        if self.reasoner.model == "deepseek-reasoner":
            Helper().generate_analysis_report(report, analysis)
        else:
            Helper().generate_analysis_report_stream(report, analysis)
        # evaluation = self.get_evaluation(analysis)
        # Helper().generate_evaluation(id, evaluation)


if __name__ == "__main__":
    if dotenv is not None:
        dotenv.load_dotenv()
    else:
        load_env_file(os.path.join(os.path.dirname(__file__), "..", ".env"))
    dmodel = os.getenv("DS_MODEL_NAME")
    # rmodel = ''
    rmodel = os.getenv("QWEN_MODEL_NAME")
    url1 = os.getenv("DS_API_URL")
    url2 = os.getenv("QWEN_API_URL")
    API_KEY1 = os.getenv("DS_API_KEY")
    API_KEY2 = os.getenv("QWEN_API_KEY")
    platform = "kernel"  # or 'kernel'
    mode = os.getenv("CISB_MODE", "legacy")

    # chater = Wrapper(dmodel, rmodel, None, API_KEY1, API_KEY1, url1, url1, platform)
    chater = Wrapper(
        dmodel,
        rmodel,
        None,
        API_KEY1,
        API_KEY2,
        url1,
        url2,
        platform,
        mode=mode,
    )
    chater.gather_prompt()

    reports = Helper().read_ids("commits.txt")
    logs = open("errors.log", "w")
    errorIds = []
    if platform == "kernel":
        print([id[:10] for id in reports], len(reports))
    else:
        print([id for id in reports], len(reports))
    print("Using reasoning model: ", rmodel)
    print("Running mode:", mode)
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
