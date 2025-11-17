from gevent import monkey
monkey.patch_all()

import os
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from reddit_remover import RedditVoteRemover, VoteType
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-in-production')

ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',')
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == ['']:
    raise ValueError("ALLOWED_ORIGINS must be set in .env file")

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
socketio = SocketIO(
    app, 
    cors_allowed_origins=ALLOWED_ORIGINS, 
    async_mode='gevent', 
    ping_timeout=60, 
    ping_interval=25,
    cors_credentials=True
)

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200

@app.errorhandler(Exception)
def handle_error(e):
    if app.config.get('DEBUG'):
        raise e
    app.logger.error(f'Unhandled exception: {str(e)}')
    return {'error': 'Internal server error'}, 500

@socketio.on('connect')
def handle_connect():
    origin = request.headers.get('Origin', '')
    if origin not in ALLOWED_ORIGINS:
        print(f'Rejected connection from untrusted origin: {origin}', flush=True)
        return False
    print('Client connected', flush=True)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected', flush=True)

@socketio.on('start_removal')
def handle_removal(data):
    cookies = data.get('cookies', '').strip()
    username = data.get('username', '').strip().replace('u/', '')
    vote_type = data.get('voteType', 'upvotes')
    
    try:
        delay = float(data.get('delay', 0.5))
    except (ValueError, TypeError):
        delay = 0.5
    
    print(f'Request from user: {username}, type: {vote_type}', flush=True)

    if not cookies or not username:
        print('Missing cookies or username! Emitting error.', flush=True)
        emit('error', {'message': 'Missing required fields: cookies and username'})
        return

    def process():
        try:
            def send_progress(message, status, stats=None):
                fixed_stats = stats or {"total": 0, "removed": 0, "failed": 0}
                emit_data = {
                    'message': message,
                    'status': status,
                    'stats': fixed_stats
                }
                if isinstance(fixed_stats, dict):
                    for key in ['post_id', 'url', 'success']:
                        if key in fixed_stats:
                            emit_data[key] = fixed_stats[key]
                socketio.emit('progress', emit_data)

            remover = RedditVoteRemover(cookies)
            result = {}

            if vote_type in ['upvotes', 'both']:
                result = remover.remove_votes(
                    username=username,
                    vote_type=VoteType.UPVOTED,
                    delay=delay,
                    progress_callback=send_progress
                )

            if vote_type in ['downvotes', 'both']:
                result = remover.remove_votes(
                    username=username,
                    vote_type=VoteType.DOWNVOTED,
                    delay=delay,
                    progress_callback=send_progress
                )

            final_stats = {"total": result.get("total", 0), "removed": result.get("removed", 0), "failed": result.get("failed", 0)}
            send_progress("✓ All done!", "success", final_stats)
            socketio.emit('complete', {'stats': final_stats})

        except Exception as e:
            app.logger.error(f'Removal error: {str(e)}')
            socketio.emit('error', {'message': 'An error occurred during removal'})

    socketio.start_background_task(target=process)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

