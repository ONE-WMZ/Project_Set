# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()  # 先创建空实例
socketio = SocketIO()  # 先创建空实例