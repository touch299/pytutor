from flask import Flask, render_template, request, jsonify
from config import Config
from core.ast_tracer import ExecutionEngine
from core.trace_formatter import format_trace
from utils.error_helper import translate_error

app = Flask(__name__)
app.config.from_object(Config)

engine = ExecutionEngine(timeout=Config.EXEC_TIMEOUT)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'trace': [], 'output': '', 'error': '代码不能为空'})
    if len(code) > Config.MAX_CODE_LENGTH:
        return jsonify({'trace': [], 'output': '', 'error': '代码过长'})

    trace_log, output = engine.run(code)
    formatted_trace = format_trace(trace_log)

    error = None
    error_step = next((s for s in trace_log if s['event'] == 'error'), None)
    if error_step:
        error = translate_error(error_step['extra'])

    return jsonify({
        'trace': formatted_trace,
        'output': output,
        'error': error
    })


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=5000)
