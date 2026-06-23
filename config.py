import os


class Config:
    EXEC_TIMEOUT = 5          # 代码执行超时（秒），防止死循环
    MAX_CODE_LENGTH = 5000    # 最大代码长度（字符）
    ERROR_TRANSLATION = True  # 是否启用报错翻译
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
