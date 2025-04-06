There is a security issue emerges after compilation in the following C code.
```c
#define LEN_SUFFIX 8
int len = len_buffer + LEN_SUFFIX;

if (len < len_buffer)
    exit(1);

char* new_buffer = (char*)malloc((size_t)len * 2);
```