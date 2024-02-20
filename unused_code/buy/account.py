import logging
import os

from tinkoff.invest import Client

TOKEN = "t.Gb6EBFHfF-eQqwR8LXYn6l7A5AM6aFh1vX9QMOmrZJ2V6OEhZdNZuW4dpThKlEH504oN2Og6HLdMXyltEBK5QQ"


def main():
    with Client(TOKEN) as client:
        accounts = client.users.get_accounts()
        print(accounts)


if __name__ == "__main__":
    main()
