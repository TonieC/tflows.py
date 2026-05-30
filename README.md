# ⚡ tflows.py

tflows.py is a lightweight automation and Discord bot framework built around a scripting engine that lets you define bot behavior using simple text-based commands instead of large boilerplate code.

It is designed for fast bot development, easy customization, and extensible command logic.

---

## 🔗 Links

- PyPI: https://pypi.org/project/tflows/
- Documentation: https://toniec.github.io/tflows
- Discord: https://discord.gg/CMSXnfcCJW
- Repository: https://github.com/toniec/tflows

---

## ✨ Features

- 🧩 Script-based command system (write bot logic as plain text)
- ⚡ Async Discord integration using discord.py
- 🔁 Event-driven execution model
- 🧠 Built-in function registry (extensible commands)
- 🔌 Modular architecture for custom features
- 📦 Lightweight design with minimal setup
- 🛠️ Debug-friendly logging system

---

## 🚀 Example
```py
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="ping",
    code="""
    send pong $ping
    log command executed
    """
)

bot.run("YOUR_TOKEN")
```
---

## 🧩 Built-in Functions

### send <message>
Sends a message to the current Discord channel.

Example:
```js
send Hello world
```
---

### log <message>
Prints a message to the console for debugging.

Example:
```js
log command executed successfully
```
---

## ⚙️ How It Works

tflows.py executes scripts using a lightweight interpreter:

- Parses command blocks line by line  
- Matches each line to a registered function  
- Resolves variables and context  
- Executes asynchronously inside Discord events  

---

## 🧠 Why Use tflows.py?

- Faster development than raw Discord.py
- No boilerplate-heavy structure
- Easy to extend with custom functions
- Ideal for automation scripting systems
- Keeps logic minimal and readable

---

## 📦 Installation

pip install tflows

---

## 📜 License

MIT License

---

## ⚡ Author

Made with ❤️ by Tonie