# bf-interpreter · 2026-09-06

零依赖 **Brainfuck 解释器**（Python 标准库），一个会话内实现完整的最小语言运行时。

## 功能

- 完整支持 8 条指令 `+ - < > [ ] , .`，其余字符自动作为注释（注意：注释文字里一旦出现这 8 个符号仍会被执行，示例文件已规避）；
- 8 位单元回绕（0~255），纸带向右自动扩展，左越界明确报错；
- 预计算括号配对跳转表，支持任意层嵌套循环；
- `,` 按字节读取输入，**EOF 时把当前单元置 0**（最常见约定，保证 `,[.,]` 回显程序可终止）；
- 括号不配对、运行期指针越界给出带位置的错误；
- CLI 支持运行 `.bf` 文件、`-e` 内联代码、`-i` 二进制输入文件。

## 运行

```bash
# 单元测试（21 个用例）
python -m unittest test_bf -v

# 运行示例：Hello World
python bf.py examples/hello.bf        # -> Hello World!

# 内联代码：cell0=2，循环两次给 cell1 加 3，输出 ASCII 0x06
python bf.py -e "++[>+++<-]>." | python -c "import sys;print(sys.stdin.buffer.read())"

# 回显示例：把输入文件内容原样输出
python bf.py examples/cat.bf -i examples/hello.bf
```

## 实现要点

- 先 `strip_comments` 过滤非法字符，再用栈一次性生成 `[`↔`]` 位置映射，执行期 O(1) 跳转；
- 纸带用 `bytearray`，加减直接 `& 0xFF` 实现回绕；
- 核心 `run(source, data) -> bytes` 与 CLI 分离，解释结果是字节串，便于单测与管道组合；
- 输出走 `sys.stdout.buffer`，避免文本编码破坏非 ASCII 字节。
