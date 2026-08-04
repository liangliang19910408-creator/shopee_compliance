"""
全局状态管理 - 避免循环导入
"""

URL_PARSE_LIMIT = {}  # {ip: {count: 0, date: 'YYYY-MM-DD'}}
URL_CACHE = {}  # {url: {title: '', desc: '', timestamp: 123}}
SCAN_LIMIT = {}  # {ip: {count: 0, hour: 'YYYY-MM-DD HH'}}
