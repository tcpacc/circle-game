import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room
import time,random,sqlite3,os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secret'
socketio = SocketIO(app, cors_allowed_origins='*')

DB_FILE = 'rooms.db'

if not os.path.exists(DB_FILE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE rooms (name TEXT PRIMARY KEY, passcode TEXT)''')
    conn.commit()
    conn.close()

WIDTH, HEIGHT = 800, 600
PLAYER_SPEED = 220.0
TICK = 1.0 / 30.0

rooms = {}
player_room = {}
usedUserNames={}

def room_exists(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT passcode FROM rooms WHERE name=?', (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def create_room_db(name, passcode):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO rooms (name, passcode) VALUES (?, ?)', (name, passcode))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join_room')
def handle_join(data):
    sid = request.sid
    room_name = (data.get('room') or '').strip()
    passcode = data.get('passcode')
    username = (data.get('username') or '').strip()

    if not room_name or passcode is None or not username:
        socketio.emit('join_error', {'error': 'Room, passcode, and username required'}, room=sid)
        return
    
    existing_passcode = room_exists(room_name)
    if existing_passcode is None:
        create_room_db(room_name, passcode)
        rooms[room_name] = { 'passcode': passcode, 'players': {} }
        rooms[room_name]['ball'] = {
            'x': WIDTH / 2,
            'y': HEIGHT / 2,
            'vx': 200,
            'vy': 200,
            'r': 15
        }
        rooms[room_name]['scores'] = {} 
    else:
        if existing_passcode != passcode:
            socketio.emit('join_error', {'error': 'Invalid passcode'}, room=sid)
            return
        if room_name not in rooms:
            rooms[room_name] = {'passcode': existing_passcode, 'players': {}}
            rooms[room_name]['ball'] = {
                'x': WIDTH / 2,
                'y': HEIGHT / 2,
                'vx': 200,
                'vy': 200,
                'r': 15
            }
            rooms[room_name]['scores'] = {} 
        
    # if sid in player_room:
    #     old_room = player_room[sid]
    #     leave_room(old_room)
    #     rooms[old_room]['players'].pop(sid, None)
    #     if not rooms[old_room]['players']:
    #         del rooms[old_room]

    # if room_name not in rooms:
    #         rooms[room_name] = {'passcode': existing_passcode or existing_passcode, 'players': {}}

    if len(rooms[room_name]['players']) >=4:
        socketio.emit('join_error', {'error': 'Room is Full'}, room=sid)
        return
    elif username in usedUserNames.values():
        socketio.emit('join_error', {'error': 'Username Already In Use'}, room=sid)
        return
    else:
        usedUserNames[sid] = username

    p = {
        'id': sid,
        'username': username,
        'x': random.uniform(50, WIDTH-50),
        'y': random.uniform(50, HEIGHT-50),
        'vx': 0.0,
        'vy': 0.0,
        'r': 18,
        'color': '#%06x' % random.randint(0, 0xFFFFFF)
    }
    rooms[room_name]['players'][sid] = p
    player_room[sid] = room_name  # NEW: Save room mapping
    join_room(room_name)
    socketio.emit('init', {'id': sid, 'w': WIDTH, 'h': HEIGHT,'room':room_name}, room=sid)
    socketio.emit('system_message', {'msg': f'{username} joined room {room_name}'}, room=room_name)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    usedUserNames.pop(sid)
    if sid in player_room:  # NEW: Ensure proper cleanup
        room_name = player_room.pop(sid)
        try:
            del rooms[room_name]['scores'][sid]
        except:
            pass
        if room_name in rooms and sid in rooms[room_name]['players']:
            rooms[room_name]['players'].pop(sid, None)
            leave_room(room_name)
            socketio.emit('state', {'room': room_name, 'players': rooms[room_name]['players'],'ball':rooms[room_name]['ball'],"scores":rooms[room_name]["scores"]}, room=room_name)
            socketio.emit('system_message', {'msg': f'Player left {room_name}'}, room=room_name)
            if not rooms[room_name]['players']:
                del rooms[room_name]

@socketio.on('input')
def handle_input(data):
    sid = request.sid
    if sid in player_room:
        room_name = player_room[sid]
        p = rooms[room_name]['players'].get(sid)
        try:
            dx = float(data.get('dx', 0))
            dy = float(data.get('dy', 0))
        except Exception:
            dx, dy = 0.0, 0.0
        mag = (dx*dx + dy*dy) ** 0.5
        nx, ny = (dx/mag, dy/mag) if mag > 0 else (0, 0)
        p['vx'] = nx * PLAYER_SPEED
        p['vy'] = ny * PLAYER_SPEED
        



def game_loop():
    last = time.time()
    while True:
        now = time.time()
        dt = now - last
        last = now
        if dt <= 0:
            socketio.sleep(TICK)
            continue

        for room_name, room_data in list(rooms.items()):
            for p in room_data['players'].values():
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['x'] = max(p['r'], min(WIDTH - p['r'], p['x']))
                p['y'] = max(p['r'], min(HEIGHT - p['r'], p['y']))
            ball = room_data['ball']
            ballSpeedMultiplier = 1.5
            ball['x'] += ball['vx'] * dt
            ball['y'] += ball['vy'] * dt

            # Bounce on players
            for sid, p in room_data['players'].items():
                dx = ball['x'] - p['x']
                dy = ball['y'] - p['y']
                dist = (dx*dx + dy*dy) ** 0.5
                if dist < ball['r'] + p['r']:
                    if p['vx'] == 0:
                    # Simple bounce: reverse velocity
                        ball['vx'] = -ball['vx']
                    else:
                        ball['vx'] = p['vx']*ballSpeedMultiplier
                    if p['vy'] == 0:
                        ball['vy'] = -ball['vy']
                    else:
                        ball['vy'] = p['vy']*ballSpeedMultiplier
                    break

            # Goals (edges)
            goal_owner_sid = None
            if ball['y'] - ball['r'] <= 0:
                if room_data['players']:
                    goal_owner_sid = list(room_data['players'].keys())[0]
                    ball['x'] = WIDTH/2
                    ball['y'] = HEIGHT/2
                ball['vy'] = -ball['vy']
            elif ball['y'] + ball['r'] >=HEIGHT:
                if len(room_data['players']) > 1:
                    goal_owner_sid = list(room_data['players'].keys())[1]
                    ball['x'] = WIDTH/2
                    ball['y'] = HEIGHT/2
                ball['vy'] = -ball['vy']
            elif ball['x'] - ball['r'] <= 0:
                if len(room_data['players']) > 2:
                    goal_owner_sid = list(room_data['players'].keys())[2]
                    ball['x'] = WIDTH/2
                    ball['y'] = HEIGHT/2
                ball['vx'] = -ball['vx']
            elif ball['x'] + ball['r'] >= WIDTH:
                if len(room_data['players']) > 3:
                    goal_owner_sid = list(room_data['players'].keys())[3]
                    ball['x'] = WIDTH/2
                    ball['y'] = HEIGHT/2
                ball['vx'] = -ball['vx']

            if goal_owner_sid:
                ball['vx'] = 0
                ball['vy'] = 0
                room_data['scores'][goal_owner_sid] = room_data['scores'].get(goal_owner_sid, 0) + 1

            # Broadcast state
            socketio.emit('state', {
                'room': room_name,
                'players': room_data['players'],
                'ball': ball,
                'scores': room_data['scores']
            }, room=room_name)


        socketio.sleep(TICK)

@socketio.on('chat_message')
def handle_chat(msg):
    sid = request.sid
    for room_name, room_data in rooms.items():
        if sid in room_data['players']:
            player = room_data['players'][sid]
            socketio.emit('chat_message', {
                'username': player['username'],
                'color': player['color'],
                'text': msg,
                'id': sid
            }, room=room_name)
            break

@socketio.on('leave_room')
def handle_leave():
    sid = request.sid
    usedUserNames.pop(sid)
    for room_name, room_data in list(rooms.items()):
        if sid in room_data['players']:
            try:
                del rooms[room_name]['scores'][sid]
            except:
                pass
            socketio.emit('system_message', {'msg': f'{room_data['players'][sid]['username']} left {room_name}'}, room=room_name)
            room_data['players'].pop(sid, None)
            leave_room(room_name)
            socketio.emit('left_room', room=sid)  # Notify client to hide chat
            if not room_data['players']:
                del rooms[room_name]
            socketio.emit('state', {'room': room_name, 'players': rooms[room_name]['players'],'ball' : room_data["ball"],'scores': room_data['scores']}, room=room_name)
            break

socketio.start_background_task(game_loop)

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000)