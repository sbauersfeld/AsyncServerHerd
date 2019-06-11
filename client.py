import asyncio
import sys
import time

server_ports = {
    'Goloman' : 12000,
    'Hands' : 12001,
    'Holiday' : 12002,
    'Welsh' : 12003,
    'Wilkes' : 12004
}

async def tcp_echo_client(message, server_name):
    reader, writer = await asyncio.open_connection(
        '127.0.0.1', server_ports[server_name])

    print(f'Send: {message!s}')
    writer.write(message.encode())
    await writer.drain()
    writer.write_eof()
    # writer.close()
    # await writer.wait_closed()

    data = await reader.read()
    print(f'Received: {data.decode()!s}')
    # print(len(data))

    # print('Close the connection')
    writer.close()

async def main():
    if len(sys.argv) != 2 or sys.argv[1] not in server_ports:
        print("Invalid input")
        sys.exit(1)
        
    tasks = []
    tasks.append(asyncio.create_task(tcp_echo_client("IAMAT kiwi.cs.ucla.edu +34.068930-118.445127 " + str(time.time()), sys.argv[1])))
    await asyncio.sleep(1)
    tasks.append(asyncio.create_task(tcp_echo_client("IAMAT k1.cs.ucla.edu +38.9023-110.343545 ", sys.argv[1])))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT singal.cs.ucla.edu +35.068930-118 1651567233.7065177 \n', "Hands")))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT steven.cs.ucla.edu +35.068930-117 1651567233 \n', sys.argv[1])))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT k2.cs.ucla.edu +35.068930117.445127 1651567233.7065177\n', sys.argv[1])))
    tasks.append(asyncio.create_task(tcp_echo_client('WHATSAT steven.cs.ucla.edu 20 2\n', "Goloman")))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT k3.cs.ucla.edu +35.068930117.445127- 1651567233.7065177\n', sys.argv[1])))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT k4.cs.ucla.edu +35.068930117.445127-12. 1651567233.7065177\n', sys.argv[1])))
    tasks.append(asyncio.create_task(tcp_echo_client('IAMAT k5.cs.ucla.edu +35.068930117.445127-12.34 1651567233.\n', sys.argv[1])))


    for task in tasks:
        await task
    await tcp_echo_client('WHATSAT kiwi.cs.ucla.edu 20 2\n', sys.argv[1])

if __name__ == '__main__':
    asyncio.run(main())