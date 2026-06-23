import ast
import sys
import signal
from io import StringIO


class TraceInjector(ast.NodeTransformer):
    """AST 插桩器，在所有关键位置注入 __trace__() 调用"""

    def _make_trace(self, event, names=None, lineno=None, extra=None):
        args = [ast.Constant(value=event)]
        args.append(ast.List(elts=[ast.Constant(n) for n in (names or [])], ctx=ast.Load()))
        args.append(ast.Constant(value=lineno))
        args.append(ast.Constant(value=extra))
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='__trace__', ctx=ast.Load()),
                args=args,
                keywords=[]
            )
        )

    def visit_Assign(self, node):
        targets = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                targets.append(t.id)
            elif isinstance(t, ast.Tuple):
                for elt in t.elts:
                    if isinstance(elt, ast.Name):
                        targets.append(elt.id)
        return [node, self._make_trace('assign', targets, node.lineno)]

    def visit_AugAssign(self, node):
        targets = [node.target.id] if isinstance(node.target, ast.Name) else ['<expr>']
        return [node, self._make_trace('assign', targets, node.lineno)]

    def visit_AnnAssign(self, node):
        if node.value:
            targets = [node.target.id] if isinstance(node.target, ast.Name) else ['<expr>']
            return [node, self._make_trace('assign', targets, node.lineno)]
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        loop_var = node.target.id if isinstance(node.target, ast.Name) else None
        node.body.insert(0, self._make_trace('loop', [loop_var] if loop_var else None, node.lineno))
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        node.body.insert(0, self._make_trace('loop', None, node.lineno))
        return node

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Name) and func.id == 'print') or \
               (isinstance(func, ast.Attribute) and func.attr == 'print'):
                return [self._make_trace('print', None, node.lineno), node]
        return node

    def visit_Import(self, node):
        return ast.Pass()

    def visit_ImportFrom(self, node):
        return ast.Pass()


class ExecutionEngine:
    """安全的代码执行与轨迹收集"""

    def __init__(self, timeout=5):
        self.timeout = timeout
        self.trace_log = []
        self._exec_env = {}

    def _safe_env(self):
        safe_builtins = {
            'print': print, 'range': range, 'len': len,
            'int': int, 'float': float, 'str': str,
            'list': list, 'dict': dict, 'tuple': tuple,
            'set': set, 'bool': bool, 'type': type,
            'True': True, 'False': False, 'None': None,
            'abs': abs, 'min': min, 'max': max,
            'sum': sum, 'round': round, 'zip': zip,
            'enumerate': enumerate, 'sorted': sorted,
            'reversed': reversed
        }
        return {"__builtins__": safe_builtins}

    def _trace_handler(self, event, names, lineno, extra):
        snapshot = {}
        if names and self._exec_env:
            for n in names:
                if n in self._exec_env:
                    snapshot[n] = repr(self._exec_env[n])
        self.trace_log.append({
            'event': event,
            'vars': snapshot,
            'line': lineno,
            'extra': extra
        })

    def run(self, code: str):
        self.trace_log = []
        self._exec_env = {}
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        output = ''
        try:
            tree = ast.parse(code)
            injector = TraceInjector()
            tree = injector.visit(tree)
            ast.fix_missing_locations(tree)
            compiled = compile(tree, '<user>', 'exec')

            exec_env = self._safe_env()
            exec_env['__trace__'] = self._trace_handler
            self._exec_env = exec_env

            def handler(signum, frame):
                raise TimeoutError("执行超时")
            try:
                signal.signal(signal.SIGALRM, handler)
                signal.alarm(self.timeout)
            except AttributeError:
                pass

            exec(compiled, exec_env, exec_env)
            output = sys.stdout.getvalue()
        except TimeoutError:
            output = sys.stdout.getvalue() + '\n[提示] 代码执行超时，请检查是否有死循环。'
        except Exception as e:
            output = sys.stdout.getvalue()
            self.trace_log.append({
                'event': 'error',
                'vars': {},
                'line': None,
                'extra': str(e)
            })
        finally:
            sys.stdout = old_stdout
            try:
                signal.alarm(0)
            except:
                pass
        return self.trace_log, output
