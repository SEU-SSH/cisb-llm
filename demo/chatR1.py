from openai import OpenAI

class chatR1:

    def __init__(self):
        self.APIKEY = ''
        self.example = "Q: There is a security issue emerges after compilation in the following C code."\
            "#define LEN_SUFFIX 8 int len = len_buffer + LEN_SUFFIX;if (len < len_buffer)exit(1);char* new_buffer = (char*)malloc((size_t)len * 2);"

        self.reasoning = 'A: Standardized Issue Summary: \
            The user reports a security issue in code after compilation. The code defines `LEN_SUFFIX` with a trailing semicolon (`#define LEN_SUFFIX 8;`), leading to a syntax error during macro expansion (`len_buffer + 8;`). The subsequent logic checks for integer overflow via `if (len < len_buffer)` and allocates memory with `malloc((size_t)len * 2)`. The compiler likely ignores the invalid semicolon (treating it as an empty statement) and compiles the code, but the overflow check is unreliable due to undefined behavior (UB) in signed integer overflow.  \
            User Intent vs. Compiler Behavior: \
            - User Expectation: The code should detect overflow via `if (len < len_buffer)` and prevent unsafe memory allocation.  \
            - Actual Compiler Behavior: The trailing semicolon in `LEN_SUFFIX` is parsed as an empty statement, allowing compilation. The overflow check is subject to UB (C11 §6.5/5), enabling optimizations that may remove the check.  \
            Gap Analysis: \
            The user assumes the overflow check is valid, but signed integer overflow is UB, making the check unreliable. The compiler’s optimization may eliminate the check entirely.  \
            Summary: \
            The compiler\'s No-UB assumption eliminated the if-check, so the malloc below is insecure. The compiler actually introduced a security bug.'

        self.prompt = "你是一个专门用于分析 Bugzilla 等平台上的 bug report 的智能助手，主要任务是判断报告是否有效说明编译器出现 bug。\
            现在你需要分步如下方式思考问题：  \
            \n首先你需要将报告者描述的情况重述为计算机行业的规范化表述，将其问题总结到200字以内。若first comment信息量太低或内容混乱，则直接结束推理并报告异常。\
            \n之后，你需要根据summary和first comment描述的输出结果和解释推测其意图，并分析用户预期的行为。\
            \n然后，从first comment信息中提取用户描述，综合代码和输出结果得到编译器实际行为。例如编译器是否存在优化，应用于什么平台，自身是什么版本。\
            \n在分析完用户预期行为和编译器实际行为之后，综合以上信息推断预期和实际的差距。\
            \n问题分析完毕后，根据status尝试给出该bug report的分类，分点说明理由并判断status是否标注正确。\
            \n归类完毕后，用一到两句话总结该bug report提供的信息和有效性，并分点给出最佳实践。\
            \n注意请不要过度推理，也不需要自由发挥。 \
            \n在输出结果前，你需要将整个推理分析过程按点总结，加入到输出结果中。 \
            \n请用英文输出。\" \
            "

        self.report = {
        "id": "106503",
        "summary": "\"const char []\" in local scope never initialized",
        "status": "RESOLVED\n          INVALID",
        "first_comment": "Given the following test program:\n\n------------\n#include <sys/uio.h>\n#include <string.h>\n\n#define WRITEL(str) \\\n\t\tdo { \\\n\t\t\twdata[wpos].iov_base = (void*)(str); \\\n\t\t\twdata[wpos].iov_len = strlen(str); \\\n\t\t\twlen += wdata[wpos].iov_len; \\\n\t\t\twpos++; \\\n\t\t} while (0)\n\nint main(int argc, char **argv)\n{\n\tstruct iovec wdata[20];\n\tunsigned int wpos = 0;\n\tssize_t wlen = 0;\n\tint i = (argc > 1) ? 1 : 0;\n\n\tWRITEL(\"foo\");\n\tif (argc) {\n\t\tconst char junk[] = \"abc\";\n\t\tWRITEL(junk + i);\n\t} else {\n\t\tconst char *junk = \"def\";\n\t\tWRITEL(junk + i);\n\t}\n\tWRITEL(\"baz\\n\");\n\n\treturn writev(1, wdata, wpos) > 0 ? 0 : 1;\n}\n------------\n\nFor gcc 10 and before, and gcc 11, 12, or 13 (b06a282921c71bbc5cab69bc515804bd80f55e92) when used with -O0, this outputs:\n\n$ ./Ch\nfooabcbaz\n\nFrom gcc 11 on when using -O1 or more it does not seem to initialize the \"junk\" buffer, so it may output random things:\n\n$ ./Ch \nfoocbaz\n$ ./Ch \nfoo\ufffdbaz\n$ ./Ch \nfoo+baz\n$ ./Ch \nfoo baz\n$ ./Ch \nfoo[baz\n\nI have seen the same behavior on both amd64 and sparc32, with distro compilers (openSUSE, Gentoo) as well as an unpatched gcc13 built with Gentoo ebuilds."
    }

    def get_response(self, report):
        client = OpenAI(api_key=self.APIKEY, base_url="")
        response = client.chat.completions.create(
            model="",
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": str(report)},
        ],
            max_tokens=1024,
            temperature=0.7,
            stream=False
        )
        #print(response.choices[0].message.content)
        return response

    def generate_analysis_report(self, one_shot=False):
        if one_shot:
            self.prompt += "\n下面是一个示例： " + self.example + self.reasoning
            filename = "example_analysis_one_shot.md"
        else:
            filename = "example_analysis_zero_shot.md"
        response = self.get_response(self.report)
        
        # filename = "./reports_r1/" + filename
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.choices[0].message.reasoning_content)
            f.write("\n\n")
            f.write(response.choices[0].message.content)
        print(f"Analysed the bug report and generate results: {filename}\n")



if __name__ == "__main__":
    #print(report['id'])
    chatr1 = chatR1()
    chatr1.generate_analysis_report()