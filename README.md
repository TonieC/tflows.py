# tflow

tflow is a lightweight automation and Discord bot framework inspired by aoi.js style syntax.

## Features
- Simple command system
- Automation engine (WIP)
- Discord bot abstraction

## Example

```python
from tflow import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="ping",
    code="pong"
)

bot.run("TOKEN")