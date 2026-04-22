import json
import os


class Helper:
    def __init__(self):
        pass

    def extract_response_text(self, response):
        """Extract text from OpenAI Responses API output with legacy fallback."""
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text

        output = getattr(response, "output", None)
        if output:
            chunks = []
            for item in output:
                contents = item.get("content", []) if isinstance(item, dict) else getattr(item, "content", [])
                for content in contents:
                    text = content.get("text") if isinstance(content, dict) else getattr(content, "text", None)
                    if text:
                        chunks.append(text)
            if chunks:
                return "".join(chunks)

        # Backward compatibility for legacy chat.completions response shape.
        if hasattr(response, "choices") and response.choices:
            message = getattr(response.choices[0], "message", None)
            if message is not None and getattr(message, "content", None):
                return message.content

        return ""

    def extract_response_json(self, response):
        return json.loads(self.extract_response_text(response))

    def normalize_report_id(self, report_id):
        report_id = str(report_id)
        return report_id[:10] if len(report_id) > 10 else report_id

    def ensure_dir(self, path):
        os.makedirs(path, exist_ok=True)
        return path

    def write_json(self, path, data):
        directory = os.path.dirname(path)
        if directory:
            self.ensure_dir(directory)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def write_text(self, path, content):
        directory = os.path.dirname(path)
        if directory:
            self.ensure_dir(directory)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def read_ids(self, filename = 'bug_ids.txt'):
        with open(filename, 'r') as f:
            ids = f.readlines()
            ids = [x.strip() for x in ids]
            return ids

    def read_bug_report(self, id, filename='bug_reports.json'):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data[id]
        
    def read_commit(self, id, filename='commits.json'):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data[id]

    def read_kernel_report(self, id, filename="commits.json"):
        try:
            return self.read_commit(id, filename=filename)
        except FileNotFoundError:
            return {"id": id}

    def read_digest(self, id):
        with open(f'{id}_digest.json', 'r') as f:
            return json.load(f)
        
    def read_analysis(self, id):
        with open(f'{id}_analysis.md', 'r', encoding='utf-8') as f:
            return f.read()
        
    def generate_digest(self, report, response):
        filename = report['id'] + "_digest.json"
        # filename = "./reports_r1/" + filename
        self.write_json(filename, self.extract_response_json(response))

        print(f"Digested the bug report and generate results: {filename}")

    def generate_analysis_report(self, report, response):
        filename = self.normalize_report_id(report["id"]) + "_analysis.md"
        # filename = "./reports_r1/" + filename
        self.write_text(
            filename,
            "[Generated summary]\n" + self.extract_response_text(response),
        )

        print(f"Analysed the bug report and generate results: {filename}")

    def generate_analysis_report_stream(self, report, response):
        if type(report['id']) == int:
            report['id'] = str(report['id'])
        filename = self.normalize_report_id(report["id"]) + "_analysis.md"
        # filename = "./reports_r1/" + filename
        reasoning_content = ""
        answer_content = ""
        for chunk in response:
            # Responses API streaming event
            chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
            if chunk_type == "response.output_text.delta":
                answer_content += chunk.get("delta", "") if isinstance(chunk, dict) else getattr(chunk, "delta", "")
                continue

            # Legacy chat.completions streaming chunk
            if hasattr(chunk, "choices") and chunk.choices:
                delta = getattr(chunk.choices[0], "delta", None)
                if delta is not None:
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning_content += delta.reasoning_content
                    if hasattr(delta, 'content') and delta.content:
                        answer_content += delta.content

        if not answer_content:
            answer_content = self.extract_response_text(response)
        self.write_text(
            filename,
            "[Reasoning process]\n"
            + reasoning_content
            + "\n\n[Generated summary]\n"
            + answer_content,
        )
        print(f"Analysed the bug report and generate results: {filename}")

    def generate_evaluation(self, id, response):
        filename = id + "_evaluation.md"

        self.write_text(filename, self.extract_response_text(response))

        print(f"Evaluated the result and generate file: {filename}")

    
