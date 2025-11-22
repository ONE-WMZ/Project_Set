from routes import app, socketio


if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        allow_unsafe_werkzeug=True,
        # async_mode='gevent',
        # cors_allowed_origins="*"
    )
