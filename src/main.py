import argparse

from server import Server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stream video source")

    parser.add_argument("-f", "--file", help="configuration file path", default="application.yml")

    args = parser.parse_args()

    server = Server(args.file)
    server.start()
