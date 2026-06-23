EVENT_MAP = {
    'assign': '变量赋值',
    'loop': '进入循环',
    'print': '输出内容',
    'error': '运行错误',
    'function_enter': '进入函数',
    'call': '函数调用',
    'return': '函数返回',
}


def format_trace(raw_trace: list) -> list:
    formatted = []
    for step in raw_trace:
        event_cn = EVENT_MAP.get(step['event'], step['event'])
        vars_list = []
        for k, v in step.get('vars', {}).items():
            display_v = v if len(v) < 30 else v[:27] + '...'
            vars_list.append({'name': k, 'value': display_v})
        formatted.append({
            'event': event_cn,
            'event_raw': step['event'],
            'line': step.get('line'),
            'vars': vars_list,
            'extra': step.get('extra')
        })
    return formatted
