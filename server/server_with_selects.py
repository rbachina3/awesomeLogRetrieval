#!/opt/homebrew/bin/python3
import sys
import os
import socket
import selectors
from typing import List, Tuple
from selectors import SelectorKey
from utils import Utils
from common import Common


class ServerWithSelect(object):

    def __init__(self) -> None:
        pass

    '''
    function to process requests from user and returns responses
    '''
    def process_request(self, query: str, log_file: str) -> bytes:

        return_code, cmds = Common.prepare_grep_shell_cmds(query, log_file)
        if return_code == 1:
            print(f"response: {cmds[0].decode()}")
            return cmds[0]
        else:
            output = b''

            # logic to add file names and match count for all the files
            if os.path.isfile(log_file):
                output = bytes(log_file, 'utf-8')
                output += b': '

            line_count = Utils.execute_shell(cmds[0].decode())
            if os.path.isfile(log_file):
                    output += line_count
                    output = output.decode().split('/')[-1]
                    output = output.strip().encode()
                    output += b'\n'
            else:
                files = line_count.decode().splitlines()
                output += files[0].split('/')[-1].strip().encode()
                for file in files[1:]:
                    output += b','
                    output += file.split('/')[-1].strip().encode()
                output += b'\n'
            
            print(f'{output}')

            logs = Utils.execute_shell(cmds[1].decode())
            output += logs
            print(f"sending {len(output)} bytes")
            return output

    '''
    function to start server on hostname and port
    '''
    def start(self, hostname, port, log_file):

        server_address = (hostname, port)

        # creating socket to listen for requests for searching logs
        log_query_socket = socket.socket()

        log_query_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # configure socket as non-blocking
        log_query_socket.setblocking(False)

        # bind and listen for connections
        log_query_socket.bind(server_address)
        log_query_socket.listen()

        # using selector to use OS event notification interface for monitoring events on socket fd
        selector = selectors.DefaultSelector()

        # register log_query_socket for READ events
        selector.register(log_query_socket, selectors.EVENT_READ)

        # dict to track clients
        clients = {}

        # main loop for handling requests
        while True:

            # wait for events on registerd socket FDs for 1 second
            events: List[Tuple[SelectorKey, int]] = selector.select(timeout=1)

            if len(events) == 0:  # select timer expired no notifications from socket FDs
                continue

            for event, mask in events:

                # Get socket from SelectorKey
                event_socket: socket.socket = event.fileobj

                if event_socket == log_query_socket:
                    # READ event from server socket must be client connection
                    client_connection, address = log_query_socket.accept()
                    # mark client connection as non-blocking
                    client_connection.setblocking(False)
                    print(f"Got a connection from {address}")
                    # register client connection for event notification
                    selector.register(client_connection, selectors.EVENT_READ)
                    # store the connection details into a dict
                    clients[client_connection] = address
                else:
                    data = event_socket.recv(Common.MAX_QUERY_SIZE)

                    if len(data) > 0:
                        print(f"Got query from {clients[event_socket]}: {data}")
                        output = self.process_request(data.decode(), log_file)
                        Utils.socket_send_bytes(event_socket, output)
                    else:  # empty data indicates that client has closed the connection
                        print(f"client {clients[event_socket]} closed connection")

                    print(f"closing client connection: {clients[event_socket]}")
                    # unregister client connection for notifications
                    selector.unregister(event_socket)
                    # remove from stored clients
                    del clients[event_socket]
                    # close connection
                    event_socket.close()


if __name__ == "__main__":

    hostname, port, log_file = Common.parse_server_cmdline_args(sys.argv[1:])

    server = ServerWithSelect()

    server.start(hostname=hostname, port=port, log_file=log_file)
