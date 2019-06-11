import sys, time, re
import asyncio, aiohttp
import json, logging

# connections contains the 'talks to' relationship for each server
connections = {
    'Goloman' : ['Hands', 'Holiday', 'Wilkes'],
    'Hands' : ['Goloman', 'Wilkes'],
    'Holiday' : ['Goloman', 'Welsh', 'Wilkes'],
    'Welsh' : ['Holiday'],
    'Wilkes' : ['Goloman', 'Hands', 'Holiday']
}

# server_ports maps each server to a port number
server_ports = {
    'Goloman' : 12000,
    'Hands' : 12001,
    'Holiday' : 12002,
    'Welsh' : 12003,
    'Wilkes' : 12004
}

# AT_... represent indices for each component of a message in AT commands
AT_ORIGIN = 1
AT_DIFF = 2
AT_CLIENT = 3
AT_COORD = 4
AT_TIME = 5
AT_SENDER = 6

# IN_... represent indices for each component of a message in IAMAT commands
IN_COMMAND = 0
IN_CLIENT = 1
IN_COORD = 2
IN_TIME = 3

# FIND_... represent indices for each component of a message in WHATSAT commands
FIND_CLIENT = 1
FIND_RANGE = 2
FIND_LIMIT = 3

# DATA_... represent indices for each data component contained in the server's dictionary of clients
DATA_SERVER = 0
DATA_DIFF = 1
DATA_COORD = 2
DATA_TIME = 3

# The Async_Server class provides functionality for running an asynchronous server
class Async_Server:
    def __init__(self, server_name):
        self.api = "" # this is my api key
        self.server_name = server_name # record the name of this server
        self.clients = {} # keep track of clients
        self.location_regex = re.compile(r"([+-]\d+\.\d+|[+-]\d+)([+-]\d+\.\d+|[+-]\d+)") # regex allows for verification of commands
        self.split_latlong = re.compile(r"([+-]\d+\.\d+|[+-]\d+)")
        self.decimal_regex = re.compile(r"(\d+\.\d+|\d+)")
        self.sign_decimal_regex = re.compile(r"([+-]\d+\.\d+|[+-]\d+)")
        self.int_regex = re.compile(r"\d+")
        logging.basicConfig(filename=f"{server_name!s}.log", filemode='w', level=logging.INFO, # setup logger
            format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S')

    # start running an asyncrhonous server
    def start(self):
        # print(f'{self.server_name} server started')
        asyncio.run(self.run_server())

    # provide an asynchronous logger
    async def log(self, level, info):
        if level == "info":
            logging.info(info)
        elif level == "warning":
            logging.warning(info)
        elif level == "critical":
            logging.critical(info)

    # this function starts up a server that receives connections and creates tasks to call the callback
    # provided to the server, which is the process client function defined below
    async def run_server(self):
        server = await asyncio.start_server(
            self.process_client, '127.0.0.1', server_ports[self.server_name])

        async with server:
            await server.serve_forever()

    # this function processes a client or received command
    async def process_client(self, reader, writer):
        data = await reader.read(-1)
        orig_msg = data.decode()
        msg = orig_msg.strip()
        message = msg.split()

        # AT commands should update client info and do not result in a response message
        if len(message) != 0 and message[IN_COMMAND] == 'AT':
            await self.log("info", "Opened connection with: " + message[AT_SENDER])
            await self.log("info", "Received message: " + msg)
            await self.log("info", "Closed connection with: " + message[AT_SENDER])
            await self.handle_at(message)
        else:
            # other commands require a response
            await self.log("info", "Received message: " + msg)
            response_message = ""
            add_newline = False
            if len(message) != 0 and message[IN_COMMAND] == 'IAMAT':
                response_message = await self.handle_iamat(message)
            elif len(message) != 0 and message[IN_COMMAND] == 'WHATSAT':
                response_message, add_newline = await self.handle_whatsat(message)

            if response_message == "":
                response_message = "? " + orig_msg

            # print(f"Send: {response_message!r}")

            await self.log("info", "Sending message: " + response_message)
            if add_newline: # it makes the logs looker nicer when second newline added after logging
                response_message += "\n"
            writer.write(response_message.encode())
            writer.write_eof()
            await writer.drain()
            # print(len(response_message))

        writer.close() # close the connection

    # update the clients if a new client is received or if the new client message is more recent than the current data
    def add_client(self, msg, origins):
        if msg[AT_CLIENT] not in self.clients or float(msg[AT_TIME]) > float(self.clients[msg[AT_CLIENT]][DATA_TIME]):
            self.clients[msg[AT_CLIENT]] = [msg[AT_ORIGIN], msg[AT_DIFF], msg[AT_COORD], msg[AT_TIME]]
            # print("added client " + msg[AT_CLIENT] + " " + str(self.clients[msg[AT_CLIENT]]))
            flood_msg = msg + [self.server_name]
            asyncio.create_task(self.flood(flood_msg, origins)) # create a task to flood the update to other servers

    # handle IAMAT commands and result the string to be sent to the client
    # if "" is returned, the command is invalid
    async def handle_iamat(self, message):
        # verify the command with regex
        if (len(message) != 4 or not self.location_regex.fullmatch(message[IN_COORD])
            or not self.decimal_regex.fullmatch(message[IN_TIME])):
            return ""

        # compute the time difference
        serv_time = time.time()
        sent_time = float(message[IN_TIME])
        diff_time = serv_time - sent_time
        if diff_time > 0:
            diff_time = "+" + str(diff_time)
        else:
            diff_time = str(diff_time)
        
        # formulate the response message
        response_message = ["AT", self.server_name, diff_time, message[IN_CLIENT], message[IN_COORD], message[IN_TIME]] 

        # update client data and flood other servers
        self.add_client(response_message, [])
        return " ".join(response_message)

    # handle WHATSAT commands and return the string to be sent back to the client
    # if "" is returned, the command was invalid
    async def handle_whatsat(self, message):
        # verify that the command is valid
        if (len(message) != 4 or not self.int_regex.fullmatch(message[FIND_RANGE] 
            or not self.int_regex.fullmatch(message[FIND_LIMIT]))):
            return "", False
        radius = int(message[FIND_RANGE])
        limit = int(message[FIND_LIMIT])
        if radius <= 0 or radius > 50 or limit < 0 or limit > 20 or message[FIND_CLIENT] not in self.clients:
            return "", False

        # compute the url to be sent to google based on the stored client's data and the whatsat command
        radius *= 1000
        client = self.clients[message[FIND_CLIENT]]
        lat_long = self.split_latlong.findall(client[DATA_COORD])
        # print(lat_long)
        request_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat_long[0]!s},{lat_long[1]!s}&radius={radius!s}&key={self.api!s}"
        # print(request_url)

        # get the requested data from google in json format
        async with aiohttp.ClientSession() as session:
            result = None
            try: # use timeout to avoid hanging lookups
                result = await asyncio.wait_for(self.fetch(session, request_url), timeout=60)
            except asyncio.TimeoutError:
                # print("Google API Server Timeout")
                return "", False

            # print(result['results'])

            # limit the number of returned results based on the command argument
            result['results'] = result['results'][:limit]
            places = json.dumps(result, indent=3)
            # print(places)
            return f"AT {client[DATA_SERVER]!s} {client[DATA_DIFF]!s} {message[FIND_CLIENT]!s} {client[DATA_COORD]!s} {client[DATA_TIME]!s}\n{places!s}\n", True
        
    # handle AT commands, record who sent the message and where it originates from to avoid infinite loops
    async def handle_at(self, message):
        # validate the at message
        if (len(message) == 7 and message[AT_ORIGIN] in server_ports and message[AT_SENDER] in server_ports
            and self.sign_decimal_regex.fullmatch(message[AT_DIFF]) and self.location_regex.fullmatch(message[AT_COORD])
            and self.decimal_regex.fullmatch(message[AT_TIME])):
            self.add_client(message[:6], [message[AT_ORIGIN], message[AT_SENDER]]) # add client and flood updates

    # send update flood messages to all servers that the current server 'talks to'
    # do not resend messages to the server that initially sent the message or the server
    # that sent the message to us; this avoids infinite loops
    async def flood(self, message, origins):
        for server in connections[self.server_name]:
            if server not in origins:
                try:
                    reader, writer = await asyncio.open_connection(
                        '127.0.0.1', server_ports[server])
                    info_message = " ".join(message)
                    await self.log("info", "Opened connection with: " + server)
                    await self.log("info", f"Sending info to {server!s}: {info_message!s}")
                    writer.write(info_message.encode())
                    writer.write_eof()
                    await writer.drain()
                    writer.close()
                    await self.log("info", "Closed connection with: " + server)
                except:
                    await self.log("warning", "Failed to open connection with: " + server)

    # get the response from google and return the data in json format
    async def fetch(self, session, url):
        async with session.get(url) as response:
            return await response.json()

# main creates a Async_Server class object and provides it with the name of the running server
# it then tells the server to start serving clients
def main():
    if len(sys.argv) != 2 or sys.argv[1] not in server_ports:
        print("Invalid server name")
        sys.exit(1)
        
    Server = Async_Server(sys.argv[1])
    Server.start()
    logging.shutdown()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard Interrupt")