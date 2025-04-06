import requests
from bs4 import BeautifulSoup
import json
import time

COUNT_URL = 'https://gcc.gnu.org/bugzilla/buglist.cgi?bug_status=UNCONFIRMED&bug_status=NEW&bug_status=ASSIGNED&bug_status=SUSPENDED&bug_status=WAITING&bug_status=REOPENED&bug_status=RESOLVED&bug_status=VERIFIED&bug_status=CLOSED&cf_known_to_fail_type=allwords&cf_known_to_work_type=allwords&chfield=%5BBug%20creation%5D&chfieldfrom=2022-01-01&chfieldto=Now&component=analyzer&component=boehm-gc&component=c&component=c%2B%2B&component=classpath&component=cp-tools&component=crypto&component=debug&component=demangler&component=driver&component=fastjar&component=gcov-profile&component=inetlib&component=inline-asm&component=ipa&component=jit&component=libbacktrace&component=libcc1&component=libf2c&component=libgcc&component=libgdiagnostics&component=libobjc&component=libquadmath&component=libstdc%2B%2B&component=lto&component=middle-end&component=modula2&component=preprocessor&component=regression&component=rtl-optimization&component=sanitizer&component=sarif-replay&component=target&component=testsuite&component=translation&component=tree-optimization&component=web&component=xml&limit=0&order=bug_id&query_format=advanced&resolution=INVALID&limit=0'
BASE_URL = "https://gcc.gnu.org/bugzilla/show_bug.cgi?id="

class ReportScraper:
    def __init__(self):
        pass

    def get_bug_ids(self):
        response = requests.get(COUNT_URL)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # 查找包含 Bug 列表的表格
            table = soup.find('table', class_='bz_buglist')
            bug_ids = []
            if table:
                # 查找表格中的所有行
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳过表头行
                    # 假设 Bug ID 位于第一列
                    bug_id_cell = row.find('td', class_="first-child bz_id_column")
                    if bug_id_cell:
                        bug_id = bug_id_cell.text.strip()
                        bug_ids.append(bug_id)
            return bug_ids
        else:
            print('Failed to retrieve the bug list page')
            return []

    def save_bug_ids_to_file(self, bug_ids, filename='bug_ids.txt'):
        with open(filename, 'a') as file:
            for bug_id in bug_ids:
                file.write(f'{bug_id}\n')
        print(f'Saved {len(bug_ids)} bug IDs to {filename}')

    # scratch comments from the websites
    def fetch_bug_report(self, bug_id):
        url = BASE_URL + bug_id
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            summary = soup.find('span', id= 'short_desc_nonedit_display').text.strip()
            status = soup.find("span", id='static_bug_status').text.strip()
            first_comment = soup.find('pre', class_='bz_comment_text').text.strip()
            # attachments = 

            return {
                'id': bug_id,
                'summary': summary,
                'status': status,
                'first_comment': first_comment
            }
        else:
            print(f'Failed to fetch bug report for ID {bug_id}')
            return None

    def get_attachments(self, soup):
        pass

    def save_to_json(self, data, filename="bug_reports2.json"):
        with open(filename, 'w') as file:
            json.dump(data, file, indent= 4)
        print(f'Saved {len(data)} bug reports to {filename}')


    def store_bug_report_as_json(self):
        # bug_reports = []
        print('Retrieving bug reports...')
        bug_reports = {}
        with open('bug_ids.txt', 'r') as file:
            bug_ids = file.read().splitlines()

        print(f'Found {len(bug_ids)} bug IDs')

        for bug_id in bug_ids:
            report = self.fetch_bug_report(bug_id)
            if report:
                bug_reports[bug_id] = report
                print(f'Fetched bug report for ID {bug_id}')
            #time.sleep(0.5)

        print(f'Fetched {len(bug_reports)} bug reports')
        self.save_to_json(bug_reports)

    def update_bug_ids(self):
        bug_ids = self.get_bug_ids()
        self.save_bug_ids_to_file(bug_ids)

    def update_bug_reports(self):
        bug_reports = {}
        with open('bug_ids_update.txt', 'r') as file:
            bug_ids = file.read().splitlines()

        for id in bug_ids:
            report = self.fetch_bug_report(id)
            if report:
                bug_reports[id] = report
                print(f'Fetched bug report for ID {id}')
        
        self.save_to_json(bug_reports, 'bug_reports_update.json')
        print(f'Fetched {len(bug_reports)} bug reports')

# 示例调用
if __name__ == "__main__":
    # update_bug_ids()
    # store_bug_report_as_json()
    helper = ReportScraper()
    helper.update_bug_reports()