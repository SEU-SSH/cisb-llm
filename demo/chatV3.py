from openai import OpenAI

APIKEY = ''
report = {
        "id": "106503",
        "summary": "\"const char []\" in local scope never initialized",
        "status": "RESOLVED\n          INVALID",
        "first_comment": "Given the following test program:\n\n------------\n#include <sys/uio.h>\n#include <string.h>\n\n#define WRITEL(str) \\\n\t\tdo { \\\n\t\t\twdata[wpos].iov_base = (void*)(str); \\\n\t\t\twdata[wpos].iov_len = strlen(str); \\\n\t\t\twlen += wdata[wpos].iov_len; \\\n\t\t\twpos++; \\\n\t\t} while (0)\n\nint main(int argc, char **argv)\n{\n\tstruct iovec wdata[20];\n\tunsigned int wpos = 0;\n\tssize_t wlen = 0;\n\tint i = (argc > 1) ? 1 : 0;\n\n\tWRITEL(\"foo\");\n\tif (argc) {\n\t\tconst char junk[] = \"abc\";\n\t\tWRITEL(junk + i);\n\t} else {\n\t\tconst char *junk = \"def\";\n\t\tWRITEL(junk + i);\n\t}\n\tWRITEL(\"baz\\n\");\n\n\treturn writev(1, wdata, wpos) > 0 ? 0 : 1;\n}\n------------\n\nFor gcc 10 and before, and gcc 11, 12, or 13 (b06a282921c71bbc5cab69bc515804bd80f55e92) when used with -O0, this outputs:\n\n$ ./Ch\nfooabcbaz\n\nFrom gcc 11 on when using -O1 or more it does not seem to initialize the \"junk\" buffer, so it may output random things:\n\n$ ./Ch \nfoocbaz\n$ ./Ch \nfoo\ufffdbaz\n$ ./Ch \nfoo+baz\n$ ./Ch \nfoo baz\n$ ./Ch \nfoo[baz\n\nI have seen the same behavior on both amd64 and sparc32, with distro compilers (openSUSE, Gentoo) as well as an unpatched gcc13 built with Gentoo ebuilds."
    }
prompt = "你是一个专门用于分析 Bugzilla 等平台上的 bug report 的智能助手，主要任务是判断报告是否有效说明编译器出现 bug。\
            提供的 report 将包含bug id，summary，status和first comment信息。分析时需要考虑以下几个维度。\
            \n1.问题描述\
            \n2.用户期望行为\
            \n3.编译器行为\
            \n4.问题分析\
            \n5.分类\
            \n6.总结和建议\
            \n请不要过度推理，也不需要自由发挥。\
            "


def get_response(report):
    client = OpenAI(api_key=APIKEY, base_url="")
    response = client.chat.completions.create(
        model="",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(report)},
    ],
        max_tokens=1024,
        temperature=0.7,
        stream=False
    )
    #print(response.choices[0].message.content)
    return response

def generate_analysis_report(report):
    response = get_response(report)
    filename = report['id'] + "_analysis.md"
    filepath = "./reports_v3/" + filename
    with open(filepath, "w", encoding="utf-8") as f:
        # f.write(response.choices[0].message.reasoning_content)
        # f.write("\n\n")
        f.write(response.choices[0].message.content)
    print(f"Analysed the bug report and generate results: {filepath}\n")

if __name__ == "__main__":
    #print(report['id'])
    generate_analysis_report(report)