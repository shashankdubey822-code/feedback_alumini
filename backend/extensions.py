from flask_socketio import SocketIO

# Configure SocketIO with increased ping limits to prevent aggressive disconnections
# manage_session=False can help prevent KeyErrors when a client force-disconnects
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25,
    manage_session=False
)
