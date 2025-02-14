import socket
from base64 import b64decode, b64encode

from core.error import ArcError, Timeout

from .constant import Constant
from .user import UserInfo

socket.setdefaulttimeout(Constant.LINKPLAY_TIMEOUT)


def get_song_unlock(client_song_map: dict) -> bytes:
    '''处理可用歌曲bit，返回bytes'''

    user_song_unlock = [0] * Constant.LINKPLAY_UNLOCK_LENGTH
    for i in range(0, Constant.LINKPLAY_UNLOCK_LENGTH*2, 2):
        x = 0
        y = 0
        if str(i) in client_song_map:
            if client_song_map[str(i)][0]:
                x += 1
            if client_song_map[str(i)][1]:
                x += 2
            if client_song_map[str(i)][2]:
                x += 4
            if client_song_map[str(i)][3]:
                x += 8
        if str(i+1) in client_song_map:
            if client_song_map[str(i+1)][0]:
                y += 1
            if client_song_map[str(i+1)][1]:
                y += 2
            if client_song_map[str(i+1)][2]:
                y += 4
            if client_song_map[str(i+1)][3]:
                y += 8

        user_song_unlock[i // 2] = y*16 + x

    return bytes(user_song_unlock)


class Player(UserInfo):
    def __init__(self, c=None, user_id=None) -> None:
        super().__init__(c, user_id)
        self.player_id: int = 0
        self.token: int = 0
        self.key: bytes = None

        self.__song_unlock: bytes = None
        self.client_song_map: dict = None

    def to_dict(self) -> dict:
        return {
            'userId': self.user_id,
            'playerId': str(self.player_id),
            'token': str(self.token),
            'key': (b64encode(self.key)).decode()
        }

    @property
    def song_unlock(self) -> bytes:
        if self.__song_unlock is None:
            self.get_song_unlock()
        return self.__song_unlock

    def get_song_unlock(self, client_song_map: dict = None) -> bytes:
        if client_song_map is not None:
            self.client_song_map = client_song_map
        self.__song_unlock = get_song_unlock(self.client_song_map)


class Room:
    def __init__(self) -> None:
        self.room_id: int = 0
        self.room_code: str = 'AAAA00'

        self.song_unlock: bytes = None

    def to_dict(self) -> dict:
        return {
            'roomId': str(self.room_id),
            'roomCode': self.room_code,
            'orderedAllowedSongs': (b64encode(self.song_unlock)).decode()
        }


class RemoteMultiPlayer:
    def __init__(self) -> None:
        self.user: 'Player' = None
        self.room: 'Room' = None

        self.data_recv: tuple = None

    def to_dict(self) -> dict:
        return dict(self.room.to_dict(), **self.user.to_dict())

    @staticmethod
    def tcp(data: str) -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((Constant.LINKPLAY_HOST,
                          Constant.LINKPLAY_TCP_PORT))
            sock.sendall(bytes(data + "\n", "utf-8"))
            try:
                received = str(sock.recv(1024), "utf-8").strip()
            except socket.timeout as e:
                raise Timeout(
                    'Timeout when waiting for data from link play server.', status=400) from e
            # print(received)
            return received

    def data_swap(self, data: tuple) -> tuple:

        received = self.tcp(Constant.LINKPLAY_AUTHENTICATION +
                            '|' + '|'.join([str(x) for x in data]))

        self.data_recv = received.split('|')
        if self.data_recv[0] != '0':
            code = int(self.data_recv[0])
            raise ArcError(f'Link Play error code: {code}', code, status=400)

    def create_room(self, user: 'Player' = None) -> None:
        '''创建房间'''
        if user is not None:
            self.user = user
        user.select_user_one_column('name')
        self.data_swap((1, self.user.name, b64encode(
            self.user.song_unlock).decode('utf-8')))
        self.room = Room()
        self.room.room_code = self.data_recv[1]
        self.room.room_id = int(self.data_recv[2])
        self.room.song_unlock = self.user.song_unlock
        self.user.token = int(self.data_recv[3])
        self.user.key = b64decode(self.data_recv[4])
        self.user.player_id = int(self.data_recv[5])

    def join_room(self, room: 'Room' = None, user: 'Player' = None) -> None:
        '''加入房间'''
        if user is not None:
            self.user = user
        if room is not None:
            self.room = room

        self.user.select_user_one_column('name')
        self.data_swap(
            (2, self.user.name, b64encode(self.user.song_unlock).decode('utf-8'), room.room_code))
        self.room.room_code = self.data_recv[1]
        self.room.room_id = int(self.data_recv[2])
        self.room.song_unlock = b64decode(self.data_recv[6])
        self.user.token = int(self.data_recv[3])
        self.user.key = b64decode(self.data_recv[4])
        self.user.player_id = int(self.data_recv[5])

    def update_room(self, user: 'Player' = None) -> None:
        '''更新房间'''
        if user is not None:
            self.user = user
        self.data_swap((3, self.user.token))
        self.room = Room()
        self.room.room_code = self.data_recv[1]
        self.room.room_id = int(self.data_recv[2])
        self.room.song_unlock = b64decode(self.data_recv[5])
        self.user.key = b64decode(self.data_recv[3])
        self.user.player_id = int(self.data_recv[4])
