"""
Chat with the two-agent bot in CMD (no web server needed).
    python cli_chat.py
Commands: /new  /debug  /exit
"""
from chat_engine import ChitkaraAssistant


def main() -> None:
    bot = ChitkaraAssistant()
    conversation_id = bot.new_conversation()
    debug = True
    print("Chitkara University Punjab Assistant\nCommands: /new  /debug  /exit\n")

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message == "/exit":
            break
        if message == "/new":
            conversation_id = bot.new_conversation()
            print("-- new conversation --\n")
            continue
        if message == "/debug":
            debug = not debug
            print(f"-- debug {'on' if debug else 'off'} --\n")
            continue

        try:
            result = bot.ask(conversation_id, message)
        except Exception as exc:
            print(f"[error] {type(exc).__name__}: {exc}\n")
            continue

        if debug:
            for i, call in enumerate(result["kb_calls"], 1):
                print(f"  [main -> KB #{i}] {call['question']}")
            if not result["kb_calls"]:
                print("  [main agent answered without the KB agent]")
        print(f"\nAssistant: {result['answer']}\n")


if __name__ == "__main__":
    main()
