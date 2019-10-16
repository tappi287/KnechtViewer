import socket
import time

from PySide2.QtCore import QObject, Signal

from modules.utils.log import init_logging

LOGGER = init_logging(__name__)

# Default parameters for Ncat class
# They shall not be modified. Provide the class instance with different parameters instead.
_TCP_IP = 'localhost'
_TCP_PORT = 3333
_BUFFER_SIZE = 4096
# Send and connect will abort after this TIMEOUT
# Recv will always wait for this TIMEOUT !
_SOCKET_TIMEOUT = 0.1
# Receive Timeout is not a socket parameter but a method condition
# Receive method will try to fetch data from socket until TIMEOUT * MULTIPLIER is reached
# or will return data if it received something and TIMEOUT*1 has passed.
_RECEIVE_TIMEOUT = 0.3
_RECEIVE_TIMEOUT_MULTIPLIER = 1.5
_ENCODING = 'utf-8'


class SocketSignals(QObject):
    send_start = Signal()
    send_end = Signal()
    recv_start = Signal()
    recv_end = Signal()
    connect_start = Signal()
    connect_end = Signal()


class Ncat:
    """
    Connects to TCP_IP, TCP_PORT and receives BUFFER_SIZE of data.
    Default to timeout mode with timeout _SOCKET_TIMEOUT.
    (Module wont continue to execute until data is send or received)

    """

    def __init__(self,
                 tcp_ip=_TCP_IP,
                 tcp_port=_TCP_PORT,
                 buffer_size=_BUFFER_SIZE,
                 socket_timeout=_SOCKET_TIMEOUT,
                 encoding=_ENCODING):
        # Initialize socket parameters
        self.server_address = (tcp_ip, tcp_port)
        self.timeout = socket_timeout
        self.buf = buffer_size
        self.enc = encoding
        self.sock = None
        self.signals = SocketSignals()

    def connect(self):
        # Create and connect the socket
        self.signals.connect_start.emit()
        try:
            self.sock = socket.create_connection(self.server_address,
                                                 self.timeout)
            LOGGER.debug('Creating socket connection to %s with timeout %s',
                         self.server_address,
                         str(self.timeout)[0:4])
        except Exception as e:
            LOGGER.warning(
                'Error: Socket connection to %s timed out in %s seconds. %s',
                self.server_address,
                str(self.timeout)[0:4],
                e)
        self.signals.connect_end.emit()

    def check_connection(self):
        self.signals.send_start.emit()
        try:
            # Check if the socket exists
            sockname = self.sock.getsockname()
        except Exception as e:
            LOGGER.error('Connection check failed, re-connecting. %s', e)
            # Re-Try connect
            self.connect()
            try:
                sockname = self.sock.getsockname()
                LOGGER.debug('Re-connected to %s', sockname)
                self.signals.send_end.emit()
                return sockname
            except Exception as e:
                LOGGER.error('Re-connect failed. %s. %s', self.sock, e)
                self.signals.send_end.emit()
                return
        # Connected
        self.signals.send_end.emit()
        return True

    def send(self, msg):
        if not self.check_connection():
            return None

        self.signals.send_start.emit()
        # Measure timeout
        send_start_time = time.time()

        # Format the message
        msg = msg.encode(self.enc)

        # Send data
        # LOGGER.info('sending %s', msg)
        total_sent = 0
        sent = 0
        msg_len = len(msg)

        # Send loop
        while total_sent < msg_len:
            try:
                sent = self.sock.send(msg[total_sent:])
            except Exception as e:
                LOGGER.error('Sending failed! - %s', e)

            if sent == 0:
                LOGGER.error('Socket communication error. Could not send: %s',
                             msg)

            total_sent = total_sent + sent
            send_time = time.time() - send_start_time
            LOGGER.debug('Sent: %s Msglen: %s - Message: %s - Duration: %s',
                         total_sent, msg_len, msg,
                         str(send_time)[0:6])

        self.signals.send_end.emit()

    def receive(self, timeout=_RECEIVE_TIMEOUT, log_empty=True):
        """
            Used for socket connection to unreliable DeltaGen host which can only
            handle one connection at a time.

            Return if data received AND timeout expired
        """
        if not self.check_connection():
            return

        self.signals.recv_start.emit()
        # total data partwise in an array
        total_data = []
        data = ''

        begin = time.time()
        while 1:
            # if you got some data, then break after timeout
            if total_data and time.time() - begin > timeout:
                recv_duration = str(time.time() - begin)[0:4]
                LOGGER.info('received %s in: %s', data.decode(self.enc),
                            recv_duration)
                break

            # if you got no data at all, wait a little longer, twice the timeout
            elif time.time() - begin > timeout * _RECEIVE_TIMEOUT_MULTIPLIER:
                if log_empty:
                    LOGGER.debug(
                        'nothing received after %s seconds. returning empty string',
                        str(timeout * _RECEIVE_TIMEOUT_MULTIPLIER)[0:4])
                break

            # recv something
            try:
                data = self.sock.recv(self.buf)
                if data:
                    total_data.append(data.decode(self.enc))
                    begin = time.time()
                else:
                    # sleep for sometime to indicate a gap
                    time.sleep(0.01)
            except Exception as e:
                if log_empty:
                    LOGGER.debug('Receive - %s', e)

        self.signals.recv_end.emit()
        # join all parts to make final string
        return ''.join(total_data)

    def receive_short_timeout(self, timeout=_RECEIVE_TIMEOUT):
        """
            Used for socket connection with reliable host's who can handle multiple connections

            Return if data received OR timeout expired
        """
        if not self.check_connection():
            return

        self.signals.recv_start.emit()
        # total data partwise in an array
        total_data = list()

        begin = time.time()
        while 1:
            # if you got some data, then break after timeout
            if total_data or time.time() - begin > timeout:
                break

            # recv something
            try:
                data = self.sock.recv(self.buf)

                if data:
                    total_data.append(data.decode(self.enc))
                    begin = time.time()
                else:
                    # sleep for sometime to indicate a gap
                    time.sleep(0.01)
            except Exception as e:
                LOGGER.debug('Short Receive - %s', e)

        self.signals.recv_end.emit()
        # join all parts to make final string
        return ''.join(total_data)

    def receive_job_data(self, timeout=_RECEIVE_TIMEOUT, end=b'End-Of-Job-Data'):
        """ Method to receive pickled binary data from Render Service Job Manager """
        if not self.check_connection():
            return None

        self.signals.recv_start.emit()
        total_data = list()
        begin = time.time()

        while True:
            if time.time() - begin > timeout:
                # Return nothing as we can not pickle incomplete data
                return None

            try:
                data = self.sock.recv(8192)
            except Exception as e:
                LOGGER.error(e)
                self.signals.recv_end.emit()
                return None

            if data is None:
                time.sleep(0.05)
                continue

            if end in data:
                total_data.append(data[:data.find(end)])
                break

            total_data.append(data)

            if len(total_data) > 1:
                # check if end_of_data was split
                last_pair = total_data[-2] + total_data[-1]

                if end in last_pair:
                    total_data[-2] = last_pair[:last_pair.find(end)]
                    total_data.pop()
                    break

        # Create one byte object from data fragments
        data = b''
        for d in total_data:
            data += d

        self.signals.recv_end.emit()
        return data

    def close(self):
        if not self.check_connection():
            return
        LOGGER.info('closing socket.')
        self.sock.close()

    def deltagen_is_alive(self, timeout=3):
        """
        Verifies that a DeltaGen host is active and alive.
        Subscribes to object 'Headlight' which should be present in any scene and modifies it's color
        to receive an event message which verfies that the host is responding.

        Will also return False if the host is active and responding but has no scene opened(therefore no Headlight).
        """
        if not self.check_connection():
            return False
        verify_msg = 'SUBSCRIBE LIGHT Headlight;LIGHT_COLOR Headlight 1.0 0.5 1.0;LIGHT_COLOR Headlight 1.0 1.0 1.0;'

        try:
            self.send(verify_msg)
        except Exception as e:
            LOGGER.debug('Error sending to DeltaGen: %s', e)
        self.signals.send_end.emit()

        # Recv loop until timeout
        self.signals.recv_start.emit()
        begin = time.time()
        while 1:
            try:
                recv_str = self.receive(0.2, False)
            except Exception as e:
                LOGGER.debug('Nothing received from DeltaGen: %s', e)

            if 'EVENT Headlight' in recv_str:
                LOGGER.info(
                    'Verified an active and responding DeltaGen socket connection.'
                )
                self.signals.recv_end.emit()
                return True

            if time.time() - begin > timeout:
                LOGGER.info('DeltaGen has not responded after %s', timeout)
                break

            time.sleep(0.2)

        self.signals.recv_end.emit()
        if recv_str == None:
            return False

        return False
