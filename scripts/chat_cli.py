import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agents.supervisor import SupervisorAgent
from app.db import SessionLocal


def main() -> None:
    agent = SupervisorAgent()
    print("上海房地产 Agent CLI，输入 exit 退出。")
    with SessionLocal() as session:
        while True:
            message = input("> ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            response = agent.handle(message, session=session)
            print(response.answer)
            if response.needs_human:
                print("[needs_human=true]")


if __name__ == "__main__":
    main()
