ERROR_MAP = {
    'SyntaxError': '你的代码语法不对，检查一下冒号、括号、引号是否配对。',
    'NameError': '你使用了一个还没有定义的变量，可能拼写错了或者忘记先赋值。',
    'TypeError': '数据类型不匹配，比如把字符串和整数直接相加，试试用 str() 或 int() 转换。',
    'IndexError': '列表索引超出范围，检查一下列表长度和索引值。',
    'KeyError': '字典里没有这个键，建议使用 dict.get() 方法安全访问。',
    'ZeroDivisionError': '除数不能为0，检查一下除法运算。',
    'ValueError': '传入的值类型不对，比如把字母转成整数。',
    'AttributeError': '对象没有这个属性或方法，可能你搞错了变量类型。',
    'IndentationError': '缩进错误，Python 对空格和 Tab 很敏感，检查一下代码缩进。',
    'ImportError': '导入模块失败，可能模块不存在或名字写错了。',
    'TimeoutError': '代码执行超时，可能存在死循环或无限递归。',
}


def translate_error(error_message: str) -> str:
    for key, value in ERROR_MAP.items():
        if key in error_message:
            return f"[{key}] {value}"
    return f"程序出错了：{error_message}"
