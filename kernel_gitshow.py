import os
import sys
import json
import subprocess

def read_commit_ids(file_path):
    """读取包含 commit ID 的 txt 文件"""
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)

def fetch_commit_info(local_repo_path, commit_id):
    """使用 git show 获取本地仓库单个 commit 的信息"""
    try:
        # 运行 git show 命令获取 message 和 diff
        result = subprocess.run(
            ['git', '-C', local_repo_path, 'show', '--no-color', commit_id],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout

        # 分离 message 和 diff
        lines = output.splitlines()
        message = []
        diff = []
        in_message = True

        for line in lines:
            if in_message and line.startswith('diff --git'):
                in_message = False
            if in_message and not line.startswith('commit ') and not line.startswith('Author:') and not line.startswith('Date:'):
                message.append(line.strip())
            elif not in_message:
                diff.append(line)

        return {
            'commit_id': commit_id,
            'message': ' '.join(message).strip(),
            'diff': '\n'.join(diff).strip()
        }
    except subprocess.CalledProcessError as e:
        print(f"Error fetching commit {commit_id}: {e}")
        return None

def save_output(output_dir, data):
    """保存结构化信息到 JSON 文件"""
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"commits.json")
    
    try:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        # print(f"Saved commit info to {output_file}")
    except Exception as e:
        print(f"Error saving output: {e}")

def main():
    # 配置
    commit_file = "commits.txt"  # 包含 commit ID 的文件
    local_repo_path = "/linux"  # 本地内核仓库路径
    output_dir = "."  # 输出目录
    
    # 验证仓库路径
    if not os.path.exists(local_repo_path):
        print(f"Error: Local repository path {local_repo_path} does not exist")
        sys.exit(1)
    
    # 读取 commit ID
    commit_ids = read_commit_ids(commit_file)
    commits = {}
    for commit_id in commit_ids:
        print(f"Processing commit: {commit_id}")
        
        # 获取 commit 信息
        commit_info = fetch_commit_info(local_repo_path, commit_id)
        if not commit_info:
            continue
            
        # 保存结果
        commits[commit_id] = commit_info
    
    # 保存所有 commit 信息到 JSON 文件
    save_output(output_dir, commits)


if __name__ == "__main__":
    main()