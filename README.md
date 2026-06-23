# PyTutor — Python 执行轨迹可视化工具

在网页上写 Python 代码，逐行查看变量如何变化。适合 Python 初学者理解代码执行过程。

## 功能

- 左侧写代码，右侧实时查看每一步执行轨迹
- 自动追踪变量赋值、循环迭代、print 输出
- 点击时间线步骤，代码行同步高亮

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python app.py

# 3. 浏览器打开
# http://127.0.0.1:5000
```

## 原理

使用 Python AST（抽象语法树）在源码中自动插入追踪代码，无需手动加 print 即可观察变量变化。

## 示例

输入：

```python
sum = 0
for i in range(3):
    sum += i
print(sum)
```

右侧显示：

| Step | 事件 | 行 |
|------|------|-----|
| sum = 0 | assign | 1 |
| i = 0 | loop | 2 |
| sum = 0 | assign | 3 |
| i = 1 | loop | 2 |
| sum = 1 | assign | 3 |
| i = 2 | loop | 2 |
| sum = 3 | assign | 3 |
| print | print | 4 |
