#!/usr/bin/env python
import getpass
import logging
import logging.handlers
import os

import ChatExchange.chatexchange.client
import ChatExchange.chatexchange.events

import re
import html


logger = logging.getLogger(__name__)

    
class Chatbot:
    def __init__(self):
        setup_logging()
        
        # Run `. setp.sh` to set the below testing environment variables

        host_id = "stackexchange.com"
        room_id = "53490"  # 53490 Contact room, 53592 test room

        if "ChatExchangeU" in os.environ:
            email = os.environ["ChatExchangeU"]
        else:
            email = input("Email: ")
        if "ChatExchangeP" in os.environ:
            password = os.environ["ChatExchangeP"]
        else:
            password = getpass.getpass("Password: ")

        self.client = ChatExchange.chatexchange.client.Client(host_id)
        self.client.login(email, password)
        self.me = self.client.get_me()

        self.room = self.client.get_room(room_id)
        self.room.join()
        self.room.watch(self.on_message)

        print("(You are now in room #%s on %s.)" % (room_id, host_id))
        
        self.online = None
        self.room.send_message("**The bot is currently online. Type `!!help` to see a list of commands.**")
        self.active = False  # is there an active game?
        self.defense = None
        self.defender = None
        self.clues = dict()
        self.room.send_message("Type `!!start <letter>` to begin")
        
        while self.client.logged_in:
            pass

    def on_message(self, message, client):
        try:
            if not isinstance(message, ChatExchange.chatexchange.events.MessagePosted):
                if isinstance(message, ChatExchange.chatexchange.events.MessageStarred)\
                   and re.match(r"^\d+ \(.+?\): <b>.+?</b>$", message.content):
                    message.message.pin(value=False)
                    print("Message unpinned")
                    return
                logger.debug("event: %r", message)
                return
            logger.debug(message.content)
            
            room = self.room
            
            if message.message.owner == self.me:
                if re.match(r"^\d+ \(.+?\): <b>.+?</b>$", message.content):
                    number = int(message.content.split()[0])
                    self.clues[number] = message.message
                    message.message.pin()
                    print("Message pinned")
                    return
                if ':' not in message.content and "defending" in message.content:
                    print(">> (%s) %s" % (message.user.name, message.content))
                    if self.defense:
                        self.defense.cancel_stars()
                    self.defense = message.message
                    message.message.pin()
                    print("Message pinned")
                    return
                if message.content == "<b>The bot is currently online. Type <code>!!help</code> to see a list of commands.</b>":
                    print(">> (%s) %s" % (message.user.name, message.content))
                    self.online = message.message
                    message.message.pin()
                    print("Message pinned")
                    return
            if message.content.startswith("<b>") and message.content.endswith("</b>"):
                # print(">> (%s) %s" % (message.user.name, message.content))
                if not self.active:
                    message.message.reply("Warning: no active game")
                    return
                if message.message.owner == self.defender:
                    message.message.reply("Warning: defenders can't give clues")
                    return
                i = 1
                while i in self.clues:
                    i += 1
                self.clues[i] = message.message
                room.send_message("{} ({}): **{}**".format(i, message.message.owner.name, markdown(message.content[3:-4])))
                return
            if re.match(r"^!!start ([a-zA-Z])$", message.content):
                print(">> (%s) %s" % (message.user.name, message.content))
                if self.active:
                    message.message.reply("Warning: there is already an active game")
                    return
                self.start(message.content[-1], message.user)
                return
            if re.match(r"^!!add ([a-zA-Z])$", message.content):
                print(">> (%s) %s" % (message.user.name, message.content))
                if not self.active:
                    message.message.reply("Warning: no active game")
                    return
                if message.message.owner != self.defender:
                    message.message.reply("Warning: attackers can't add letters")
                    return
                self.add(message.content[-1])
                return
            if re.match(r"^!!unstar \d+$", message.content):
                print(">> (%s) %s" % (message.user.name, message.content))
                if not self.active:
                    message.message.reply("Warning: no active game")
                    return
                number = int(message.content[9:])
                if number not in self.clues:
                    message.message.reply("Warning: no clue with that number exists")
                    return
                else:
                    self.clues[number].cancel_stars()
                    del self.clues[number]
                    return
                return
            if message.content == "!!help":
                print(">> (%s) %s" % (message.user.name, message.content))
                self.help()
                return
            if message.content == "!!reset":
                print(">> (%s) %s" % (message.user.name, message.content))
                if not self.active:
                    message.message.reply("Warning: no active game")
                    return
                self.reset()
                return
            if message.content == "!!shutdown":
                print(">> (%s) %s" % (message.user.name, message.content))
                self.shutdown()
                return
            if message.content.startswith("!!"):
                message.message.reply("Warning: invalid command. Type `!!help` to see a list of commands.")
        except Exception as e:
            self.room.send_message("An error occured: " + str(e))
            self.shutdown()
    
    def start(self, letter, user):
        self.active = True
        self.letters = letter.upper()
        self.defender = user
        self.room.send_message("{} defending **{}**".format(user.name, letter))
    
    def add(self, letter):
        self.letters += ' ' + letter.upper()
        self.room.send_message("{} defending **{}**".format(self.defender.name, self.letters))
    
    def reset(self):
        self.active = False
        self.room.send_message("Resetting...")
        for clue in self.clues.values():
            clue.cancel_stars()
        self.clues = dict()
        self.defender = None
        self.defense.cancel_stars()
        self.defense = None
        self.letters = None
        self.room.send_message("Type `!!start <letter>` to begin, or `!!help` for a list of commands")
    
    def help(self):
        self.room.send_message("""**Defender**:
To start a game, type `!!start <letter>`.
To reveal a letter, type `!!add <letter>`.
To end the game, type `!!reset`.
**Attackers**:
All clues should be in bold. The bot will automatically assign a number to the clue.
**Everyone**:
To unstar a clue, type `!!unstar <number>`.
To disable the bot, type `!!shutdown`.
To see this message again, type `!!help`.""")
    
    def shutdown(self):
        self.room.send_message("Shutting down...")
        self.online.cancel_stars()
        self.room.leave()
        self.client.logout()


def setup_logging():
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.DEBUG)

    # In addition to the basic stderr logging configured globally
    # above, we'll use a log file for chatexchange.client.
    wrapper_logger = logging.getLogger('chatexchange.client')
    wrapper_handler = logging.handlers.TimedRotatingFileHandler(
        filename='client.log',
        when='midnight', delay=True, utc=True, backupCount=7,
    )
    wrapper_handler.setFormatter(logging.Formatter(
        "%(asctime)s: %(levelname)s: %(threadName)s: %(message)s"
    ))
    wrapper_logger.addHandler(wrapper_handler)


def markdown(html_text):
    html_text = html_text.replace('*', r"\*")
    formatting = {"<b>": "**", "</b>": "**", "<i>": '*', "</i>": '*',
                  "<strike>": "---", "</strike>": "---", "<code>": '`', "</code>": '`'}
    for key, value in formatting.items():
        html_text = html_text.replace(key, value)
    return html.unescape(html_text)

    
if __name__ == "__main__":
    Chatbot()
        
