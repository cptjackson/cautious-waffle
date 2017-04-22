import os
import time
import sqlite3
from slackclient import SlackClient

#periodtracker's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

#constants
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

# Table rows
USER_ID = 0
IDENT = 1
TOTAL = 2

#global variable wtf
bot_on = False

#instantiate Slack and Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

# Database structure:
#   user (text)     id (text)     total (integer)

def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    #response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
    #"* command with numbers, delimited by spaces."

    global bot_on

    if command.startswith('help'):
        response = "@ me with these commands: "
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)
        response = "on: turn on verbal responses"
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)
        response = "off: turn off verbal responses"
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)
        response = "status: report the number of periods used (men only)"
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)
        response = " identify [m|f|o]: identify as male, female or other"
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)

    if command.startswith('on'):
        if bot_on:
            response = "I'm already on!"
        else:
            response = "You asked for it..."
            bot_on = True
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)

    if command.startswith('off'):
        if bot_on:
            response = "Aww man. Fine, I'll shut up."
            bot_on = False
        else:
            response = "..."
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)

    if command.startswith('status'):

        # Query database
        conn = sqlite3.connect("perioddb.db")
        cursor = conn.cursor()

        sql = "SELECT * FROM periods WHERE user=\'" + user + "\'"
        cursor.execute(sql)
        row = cursor.fetchall()
        num = row[0][TOTAL]
        isMale = row[0][IDENT] == 'm'

        if isMale:
            response = "Number of periods for <@" + user + ">: " + str(num)
        else:
            response = "Sorry, I only track the periods of people who " \
                "identify as male."
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)

    if command.startswith('identify '):

        conn = sqlite3.connect("perioddb.db")
        cursor = conn.cursor()

        # Male or female or something else?
        args = command.split(" ")
        if args[1] == "m":
            sql = "UPDATE periods SET id=\'m\' WHERE user=\'" + user + "\'"
            cursor.execute(sql)
            conn.commit()
            response = "Hi, <@" + user + ">! You now identify as male! Your " \
                "periods will now be tracked."
        elif args[1] == "f":
            sql = "UPDATE periods SET id=\'f\' WHERE user=\'" + user + "\'"
            cursor.execute(sql)
            conn.commit()
            response = "Hi, <@" + user + ">! You now identify as female! Your" \
                " periods will not be tracked."
        elif args[1] == "o":
            sql = "UPDATE periods SET id=\'o\' WHERE user=\'" + user + "\'"
            cursor.execute(sql)
            conn.commit()
            response = "Hi, <@" + user + ">! You now identify as other! Your" \
                " periods will not be tracked."
        else:
            response = "Sorry <@" + user + ">, I didn't quite catch that."

        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)


def respond_to_period(user, channel, num):
    """
        Tells a user they used a period and updates the
        period database.
    """

    # Query database
    conn = sqlite3.connect("perioddb.db")
    cursor = conn.cursor()

    sql = "SELECT * FROM periods WHERE user=\'" + user + "\'"
    cursor.execute(sql)
    row = cursor.fetchall()
    isMale = True

    if row:
        # User exists so add the number of periods to the total
        newNum = row[0][TOTAL] + num
        sql = "UPDATE periods SET total=" + str(newNum) + " WHERE user=\'" \
            + user + "\'"
        if row[0][IDENT] != 'm':
            isMale = False

    else:
        # User does not exist, so make a new user
        sql = "INSERT INTO periods VALUES (\'" + user + "\', \'m\', 0)"

    cursor.execute(sql)
    conn.commit()

    # Respond verbally if bot is on
    if bot_on and user != BOT_ID and isMale:
        response = "<@" + user + ">" + " You just used a period."
        slack_client.api_call("chat.postMessage", channel=channel,
                              text=response, as_user=True)

def parse_slack_output(slack_rtm_output):
    """
        Read the events firehose and do stuff.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output:

                # Detect periods
                if '.' in output['text']:

                    # Count periods
                    numPeriods = output['text'].count('.')

                    # Determine user and respond
                    user = output['user']
                    respond_to_period(user, output['channel'], numPeriods)

                if AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    return output['text'].split(AT_BOT)[1].strip().lower(), \
                           output['channel'], output['user']
    return None, None, None

if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("PeriodTracker connected and running!")
        while True:
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command,channel,user)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
