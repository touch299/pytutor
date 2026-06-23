import ast
import sys
import signal
import threading
from io import StringIO
from flask import Flask, request, render_template, jsonify

app = Flask(__name__)

# ============================================
# 安全的执行环境构建器
# ============================================
def make_safe_env():
    """返回一个受限制的全局环境，禁止危险操作"""
    safe_builtins = {
        'print': print,
        'range': range,
        'len': len,
        'int': int,
        'float': float,
        'str': str,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'bool': bool,
        'type': type,
        'isinstance': isinstance,
        'True': True,
        'False': False,
        'None': None,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
        'zip': zip,
        'enumerate': enumerate,
        'sorted': sorted,
        'reversed': reversed,
        '__import__': __import__,  # 但我们会在 AST 里禁用 import
    }
    return {"__builtins__": safe_builtins}

# ============================================
# TraceTransformer：AST 插桩
# ============================================
class TraceTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.call_stack = []  # 用于记录函数调用栈（仅用于追踪，不参与执行）

    def _make_trace_call(self, event, names=None, lineno=None, extra=None):
        args = [ast.Constant(value=event)]
        if names is not None:
            args.append(ast.List(elts=[ast.Constant(value=n) for n in names], ctx=ast.Load()))
        else:
            args.append(ast.Constant(value=None))
        args.append(ast.Constant(value=lineno))
        args.append(ast.Constant(value=extra))  # 额外信息（如函数名）
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='__trace__', ctx=ast.Load()),
                args=args,
                keywords=[]
            )
        )

    # ---------- 赋值语句 ----------
    def visit_Assign(self, node):
        targets = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                targets.append(t.id)
            elif isinstance(t, ast.Tuple):
                for elt in t.elts:
                    if isinstance(elt, ast.Name):
                        targets.append(elt.id)
            elif isinstance(t, ast.Subscript):
                # 下标赋值，无法直接获取变量名，用一个描述代替
                if isinstance(t.value, ast.Name):
                    targets.append(f"{t.value.id}[...]")
                else:
                    targets.append("<subscript>")
            elif isinstance(t, ast.Attribute):
                if isinstance(t.value, ast.Name):
                    targets.append(f"{t.value.id}.{t.attr}")
                else:
                    targets.append(f"<attribute:{t.attr}>")
        trace = self._make_trace_call("assign", targets if targets else ["<expr>"], node.lineno)
        return [node, trace]

    # ---------- 增强赋值（a += 1）----------
    def visit_AugAssign(self, node):
        targets = []
        if isinstance(node.target, ast.Name):
            targets.append(node.target.id)
        elif isinstance(node.target, ast.Subscript):
            if isinstance(node.target.value, ast.Name):
                targets.append(f"{node.target.value.id}[...]")
            else:
                targets.append("<subscript>")
        elif isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name):
                targets.append(f"{node.target.value.id}.{node.target.attr}")
            else:
                targets.append(f"<attribute:{node.target.attr}>")
        trace = self._make_trace_call("assign", targets if targets else ["<expr>"], node.lineno)
        return [node, trace]

    # ---------- 带类型注解的赋值（a: int = 1）----------
    def visit_AnnAssign(self, node):
        if node.value is not None:
            targets = []
            if isinstance(node.target, ast.Name):
                targets.append(node.target.id)
            trace = self._make_trace_call("assign", targets if targets else ["<expr>"], node.lineno)
            return [node, trace]
        return node

    # ---------- for 循环 ----------
    def visit_For(self, node):
        self.generic_visit(node)
        loop_var = None
        if isinstance(node.target, ast.Name):
            loop_var = node.target.id
        trace = self._make_trace_call("loop", [loop_var] if loop_var else None, node.lineno)
        node.body.insert(0, trace)
        return node

    # ---------- while 循环 ----------
    def visit_While(self, node):
        self.generic_visit(node)
        trace = self._make_trace_call("loop", None, node.lineno)
        node.body.insert(0, trace)
        return node

    # ---------- 输出调用（print 等）----------
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            func = node.value.func
            # 检测函数名，支持 print、print(...)、builtins.print(...)
            if (isinstance(func, ast.Name) and func.id == 'print') or \
               (isinstance(func, ast.Attribute) and func.attr == 'print'):
                trace = self._make_trace_call("print", None, node.lineno)
                return [trace, node]
        return node

    # ---------- 函数定义 ----------
    def visit_FunctionDef(self, node):
        # 记录函数名和参数
        param_names = [arg.arg for arg in node.args.args]
        enter_trace = self._make_trace_call("function_enter", param_names, node.lineno, node.name)
        # 插入到函数体开头
        pos = 1 if (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)) else 0
        node.body.insert(pos, enter_trace)
        self.generic_visit(node)
        return node

    # ---------- return 语句 ----------
    def visit_Return(self, node):
        names = []
        if node.value:
            if isinstance(node.value, ast.Name):
                names.append(node.value.id)
            elif isinstance(node.value, ast.Constant):
                names.append(repr(node.value))
        trace = self._make_trace_call("return", names if names else None, node.lineno)
        return [trace, node]

    # ---------- import 语句：直接禁止（改为 pass）----------
    def visit_Import(self, node):
        return ast.Pass()
    def visit_ImportFrom(self, node):
        return ast.Pass()

# ============================================
# 执行与跟踪
# ============================================
def run_instrumented(code):
    TRACE_LOG = []
    exec_env = make_safe_env()

    def __trace__(event, names=None, lineno=None, extra=None):
        snapshot = {}
        if names:
            for n in names:
                if n in exec_env:
                    snapshot[n] = repr(exec_env[n])
        TRACE_LOG.append({
            "event": event,
            "vars": snapshot,
            "line": lineno,
            "extra": extra
        })

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    output = ""
    try:
        # 解析与插桩
        tree = ast.parse(code)
        transformer = TraceTransformer()
        tree = transformer.visit(tree)
        ast.fix_missing_locations(tree)
        compiled = compile(tree, "<user_code>", "exec")

        exec_env['__trace__'] = __trace__

        # 超时保护（Unix 用 signal，Windows 用线程）
        def handler(signum, frame):
            raise TimeoutError("代码执行超时（超过2秒）")
        try:
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(2)  # 2秒超时
        except AttributeError:
            # Windows 不支持 SIGALRM，简单略过
            pass

        exec(compiled, exec_env, exec_env)
        output = sys.stdout.getvalue()
    except TimeoutError as e:
        output = sys.stdout.getvalue() + f"\n[超时] {e}"
    except Exception as e:
        output = sys.stdout.getvalue()
        TRACE_LOG.append({
            "event": "error",
            "vars": {},
            "line": None,
            "extra": str(e)
        })
    finally:
        sys.stdout = old_stdout
        try:
            signal.alarm(0)  # 取消超时
        except:
            pass

    return {
        "trace": TRACE_LOG,
        "output": output,
        "error": next((t.get("extra") for t in TRACE_LOG if t["event"] == "error"), None)
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    code = data.get('code', '')
    result = run_instrumented(code)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)