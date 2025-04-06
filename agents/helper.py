import json

class Helper:
    def __init__(self):
        pass

    def read_bug_report(self, id):
        with open(f'bug_reports.json', 'r') as f:
            data = json.load(f)
            return data[id]
    
    def read_digest(self, id):
        with open(f'{id}_digest.json', 'r') as f:
            return json.load(f)
        
    def read_analysis(self, id):
        with open(f'{id}_analysis.md', 'r', encoding='utf-8') as f:
            return f.read()
        
    def generate_digest(self, report, response):
        filename = report['id'] + "_digest.json"
        # filename = "./reports_r1/" + filename
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(json.loads(response.choices[0].message.content), f, indent=4)
        
        print(f"Digested the bug report and generate results: {filename}")

    def generate_analysis_report(self, report, response):
        filename = report['id'] + "_analysis.md"
        # filename = "./reports_r1/" + filename
        with open(filename, "w", encoding="utf-8") as f:
            f.write("[Reasoning process]\n")
            f.write(response.choices[0].message.reasoning_content)
            f.write("\n\n[Generated summary]\n")
            f.write(response.choices[0].message.content)

        print(f"Analysed the bug report and generate results: {filename}")

    def generate_evaluation(self, id, response):
        filename = id + "_evaluation.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.choices[0].message.content)
        
        print(f"Evaluated the result and generate file: {filename}")

    