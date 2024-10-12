![](assets/senshawigglefast.gif) # SneshBot Commands ![](assets/senshawigglefast.gif)

Please note that I use @ username and UserID interchangeably since I have included a parser that will deal with both in all the commands. If you don't know how to get UserID for a user, I suggest you familiarize yourself with it by reading: <https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID>. 

## Moderation actions

`!warn weight @username reason` - Gives a warn with weight `weight` to a user. Weight if optional. If not included, weight is 1. Warns expire after 30 days. They do not disappear from the warnlog but go from active warns to just warns. Warn level depends on the severity of the rule breach. 

- 1 active warn does nothing - just sends a dm with the warn message and logs it. 
- 2 active warns means a 24hr timeout. 
- 3 active warns is a ban. 

You can use weight 9398383202 if you want, that will still be a ban since a ban is enacted when a user has at least 3 active warns and not exactly 3 warns. 

`!warnc @username WarnIndex` - Clears warns for username. Default is clear all warns, but can include WarnIndex to clear only a specific warn. 

`!warnlog @username` - Shows list of warns for a particular user. Still works if the user is no longer in the server. 

`!dm @username **subject** message` - please use in here for easier tracking (that's where the answer will come anyways) https://discord.com/channels/1211056047784198186/1283410674915082374. Subject is an optional argument, if you want to use it you have to use the `** **` syntax. 

`!post ChannelID message` - Posts a message in a channel using SneshBot. Can be used to give verbal clarifications without using our own accounts. Very useful to look more unbiased and professional. Supports pinging users. 
 
`!preban @username` - puts on the ban list even if the user is not in the server. Doesn't send a DM. 

### Not too useful commands, still exist 

`!unban @username` - Unban a user

`!ban @username duration reason` - ban. I __strongly__ suggest using !warn 3 instead as this will log something in the warnlog and doesn't require a duration. Otherwise can always use `!preban`.

`!timeout @username duration reason` - Reason is optional. Duration must be in that format: 1w3d5h30m20s. I advise we use warn 2 instead.


## Expressions

`!exas "!trigger" message` - Creates a command for all the users to use. Gives it a unique ID as well. The `!trigger` has to be surrounded by `"" ""`. In order for the command to ping a user, add `%target%` in your message where you would like the user to be pinged. If no user is specified when the command is called, the space will just be blank. 

`!exadelete CommandID` - Deletes a command. 

`!examodify CommandID newmessage` - Changes the message from a command. 

`!exalist` - Gives full list of all commands. 

`!examod CommandID` - makes a command accessible to mod team only.


## Fun commands

`!avatarget @username` - Use to get the avatar from a user. Gives better format than Dyno and includes a link to open directly.

`!roll` - Rolls a d20 and sends a funny message. Reworked to guarantee certain rolls to be funnier. 

`!remindme timeframe message` - sends a reminder with your message as a direct reply to your command. 

`!remindmedm timeframe message` -  sends a reminder with your message as a dm.

`!reminderslist` - displays a list of the reminders you personally set. 

NOTE: For now, timeframe is only able to handle things in XdXhXmXs format. It can also recognize "tomorrow".

## Troubleshooting

Tbh just call me. Not like I am not gonna be here in a few hours max. 

The code is fully open source and available here: <https://github.com/senshastic/SenshaBot>. You are welcome to submit a pull request if you want to add anything.


### Emotes 

I can add emotes for the bot to use, just ask me which ones you want. ![](assets/senshawigglefast.gif)



