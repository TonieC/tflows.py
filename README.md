# ⚡ tflows.py

tflows.py is a lightweight automation and Discord bot framework that lets you build bots using a simple scripting system.

[Check Releases](https://pypi.org/project/tflows/)

---

## ✨ Features

- ⚡ Simple command system  
- 🧠 Built-in function engine  
- 🔁 Event-based execution  
- 🔌 Extensible architecture (add your own functions)  
- 📦 Easy to install via pip  

---

## 🚀 Example

```python
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="ping",
    code=\"\"\"
send pong
log command executed
\"\"\"
)

bot.run("YOUR_TOKEN")
```

# 🧩 Built-in Functions
send <message> → sends a message in chat
log <message> → prints to console

Example:
```
send Hello world
log This ran successfully
```

# 📦 Installation
```
pip install tflows.py
```

# 🛠️ How It Works

tflows.py uses a simple scripting engine that:
- Parses command strings line by line
- Maps commands to registered Python functions
- Executes them asynchronously inside Discord events


# 🧠 Why use tflows.py?
Build bots faster
No complex boilerplate
Focus on logic, not setup
Easily extendable for automation systems

# 📜 License
MIT License

# ⚡ Author

Made with ❤️ by Tonie