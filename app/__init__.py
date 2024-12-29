from flask import Flask
from flask_cors import CORS
from .config import Config
from .routes import api
import urllib3
import os

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用系统代理
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 如果不需要代理,请设置
os.environ['NO_PROXY'] = '60.174.207.65:8900'  # GitLab服务器地址

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    
    app.register_blueprint(api, url_prefix='/api')
    return app 