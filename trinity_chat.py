import os
import sys

def main():
    print("🧞‍♀️ Trinity Silent Text Interface")
    print("Hier kannst du Trinity leise tippen, ohne dass es jemand im Raum hört.")
    print("Tippe 'exit' zum Beenden.\n")
    
    cmd_file = os.path.join(os.path.dirname(__file__), "core", "cmd.txt")
    
    while True:
        try:
            user_input = input("Du: ")
            if user_input.strip().lower() == 'exit':
                break
                
            if user_input.strip():
                with open(cmd_file, "w", encoding="utf-8") as f:
                    f.write(user_input.strip())
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
