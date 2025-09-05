from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

global level_compledted, level, players, destroyed_bricks, bullets, data_msg
level_compledted = [
    "WWWWWWWWWWWWWWWWWWWWWWWWWW",
    "W           WW           W",
    "W           WW           W",
    "W     WW    WW    WW     W",
    "W     WW    WW    WW     W",
    "W         LLWWLL         W",
    "W        LLLWWLLL        W",
    "W     WWLLLLWWLLLLWW     W",
    "W     WWLLLLWWLLLLWW     W",
    "W        WWWWWWWW        W",
    "W           OO           W",
    "WCCCCCCCCCCCOOCCCCCCCCCCCW",
    "WOOOOOOOOOCCOOCCOOOOOOOOOW",
    "WOOOOOOOOOCCOOCCOOOOOOOOOW",
    "WCCCCCCCCCCCOOCCCCCCCCCCCW",
    "W           OO           W",
    "W        WWWWWWWW        W",
    "W     WWLLLLLLLLLLWW     W",
    "W     WWLLLLLLLLLLWW     W",
    "W        LLLWWLLL        W",
    "W         LLWWLL         W",
    "W     WW    LL    WW     W",
    "W     WW          WW     W",
    "W                        W",
    "W                        W",
    "WWWWWWWWWWWWWWWWWWWWWWWWWW",
]
level = [list(row) for row in level_compledted]

players = {}
destroyed_bricks = []
bullets = []
data_msg = []  # historia wiadomości od serwera

@socketio.on('connect')
def handle_connect():
    emit('level', {'mapa': [''.join(row) for row in level], 'destroyed_bricks': destroyed_bricks, 'bullets': bullets, 'players': players})

@socketio.on('bullet_fired')
def handle_bullet_fired(data):
    bullets.append(data)
    #print('WYSYŁAM MAPĘ:', [''.join(row) for row in level])
    emit('game_state', {
        'players': players,
        'bullets': bullets,
        'destroyed_bricks': destroyed_bricks,
        'mapa': [''.join(row) for row in level],
    })

@socketio.on('chat_message')
def handle_chat_message(data):
    # Jeśli to komunikat serwera (np. śmierć gracza), dodaj do historii i wyślij
    if isinstance(data, str):
        data_msg.append(data)
        emit('chat_message', {'name': 'SERVER', 'msg': data}, broadcast=True)
    else:
        # Normalna wiadomość gracza
        emit('chat_message', data, broadcast=True)

@socketio.on('player_update')
def handle_player_update(data):
    pid = data['id']
    if pid not in players:
        players[pid] = {
            'id': pid,
            'name': data['name'],
            'x': data['x'],
            'y': data['y'],
            'dir': data['dir'],
            'status': 'playing',
            'health': 3
        }
        print("Nowy gracz dołączył:", data['name'], "ID:", data['id'])
        data_msg.append(f"Gracz {data['name']} dołączył!")
    else:
        players[pid]['x'] = data['x']
        players[pid]['y'] = data['y']
        players[pid]['dir'] = data['dir']
        players[pid]['name'] = data['name']
    # NIE nadpisuj health ani status danymi od klienta!
    emit('game_state', {
        'players': players,
        'bullets': bullets,
        'destroyed_bricks': destroyed_bricks,
        'mapa': [''.join(row) for row in level],
    })

@socketio.on('disconnect')
def handle_disconnect():
    global level_compledted, level, players, destroyed_bricks, bullets
    # Usuń gracza po rozłączeniu
    for pid, pdata in list(players.items()):
        del players[pid]
        # zapisz kto się rozłączył do listy wiadomości
        data_msg.append(f"Gracz {pdata['name']} odszedł!")

    #print('WYSYŁAM MAPĘ:', [''.join(row) for row in level])
    emit('game_state', {
        'players': players,
        'bullets': bullets,
        'destroyed_bricks': destroyed_bricks,
        'mapa': [''.join(row) for row in level],
    })
    print("Gracz rozłączony. Obecni gracze:", list(players.keys()))

    if players == {}:
        destroyed_bricks.clear()
        bullets.clear()
        level = [list(row) for row in level_compledted]
        print('MAPA ZRESETOWANA')

import threading
import time
import random

def bullets_tick():
    global bullets
    while True:
        changed = False
        for b in bullets[:]:
            if b['dir'] == 'up':
                b['y'] -= 8
            elif b['dir'] == 'down':
                b['y'] += 8
            elif b['dir'] == 'left':
                b['x'] -= 8
            elif b['dir'] == 'right':
                b['x'] += 8
            # Kolizja z mapą
            tx = int(b['x'] // 30)
            ty = int(b['y'] // 30)
            if (
                ty < 0 or ty >= len(level) or
                tx < 0 or tx >= len(level[0]) or
                level[ty][tx] == 'W'
            ):
                bullets.remove(b)
                changed = True
                continue
            if level[ty][tx] == 'C':
                _ = random.randint(0, 9)
                if _ == 0:
                    level[ty][tx] = 'W'  # Czasem cegła staje się ścianą
                else:
                    level[ty][tx] = ' '  # Zmień cegłę na puste pole
                bullets.remove(b)
                changed = True
                continue
            # Kolizja z innymi graczami
            for pid, pdata in players.items():
                if (pdata['x'] < b['x'] < pdata['x'] + 30) and (pdata['y'] < b['y'] < pdata['y'] + 30):
                    pdata['health'] -= 1
                    if pdata['health'] <= 0:
                        players[pid]['status'] = 'lost'
                        print(f"Gracz {pdata['name']} zginął!")
                        # Wyślij komunikat na czat:
                        socketio.emit('chat_message', {'name': 'SERVER', 'msg': f"Gracz {pdata['name']} zginął!"})
                        
                        players[pid]['health'] = 3  # reset zdrowia na przyszłość
                    bullets.remove(b)
                    changed = True
                    break
        if changed:
            #print('WYSYŁAM MAPĘ:', [''.join(row) for row in level])
            socketio.emit('game_state', {
                'players': players,
                'bullets': bullets,
                'destroyed_bricks': destroyed_bricks,
                'mapa': [''.join(row) for row in level],
            })
        time.sleep(0.03)  # 30 ms

threading.Thread(target=bullets_tick, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=6789)