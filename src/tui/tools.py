
import sys
import termios
import tty

# ANSI Color Codes & UI Elements

RED        = "\033[31m"
GREEN      = "\033[32m"
LIGHT_GRAY = "\033[37m"
GRAY       = "\033[90m"
YELLOW     = "\033[33m"
CYAN       = "\033[36m"
RESET      = "\033[0m"

BOLD       = "\033[1m"
UNDERLINE  = "\033[4m"
CLEAR_LINE = "\033[2K\r"

class TuiTools:

    def keypress(self) -> str:
        """Reads a single key from the terminal without waiting for enter."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == "\x1b": ch += sys.stdin.read(2)
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def confirm(self) -> bool:
        """Show interactive menu with arrow keys and y/n input."""
        options = ["Yes", "No"]
        current_idx = 0
        sys.stderr.write("\033[?25l")
        sys.stderr.flush()

        try:
            while True:
                render_str = f"Execute:{RESET} "
                for idx, opt in enumerate(options):
                    if idx == current_idx:
                        render_str += f" {BOLD}▶{RESET} {opt}  "
                    else: render_str += f"   {opt}  "

                sys.stderr.write(f"{CLEAR_LINE}{render_str}")
                sys.stderr.flush()
                key = self.keypress()

                if key.lower() in {"y", "e"}:
                    sys.stderr.write(CLEAR_LINE)
                    return True
                if key.lower() in {"n", "q", "\x03"}:
                    sys.stderr.write(CLEAR_LINE)
                    return False
                elif key == "\x1b[D": current_idx = 0
                elif key == "\x1b[C": current_idx = 1
                elif key in {"\r", "\n", " "}:
                    sys.stderr.write(CLEAR_LINE)
                    return current_idx == 0
        
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        finally:
            # Restore cursor visibility
            sys.stderr.write("\033[?25h")
            sys.stderr.flush()
          
                
    def multi_choice(self, prompt: str, choices, menu: str, additional) -> int:
        """
        Displays an multi-choice menu selection.
        Reads a single char execution choice and fires a recursive subprocess call.
        """
        
        if choices: print(f"{prompt}:\n")
            
        i = 1
        for c in choices:
            print(f"{i}) {GRAY}{c}{RESET}")
            i += 1
        
        if choices: print()
        
        max_range = len(choices)
        print(menu, end=' ', flush=True)

        try:
            while True:
                raw_choice = self.keypress()
                choice = raw_choice.lower().strip()           
                
                print(choice if choice else raw_choice.strip())

                if choice == str(additional).lower(): return max_range + 1
                if choice == 'q' or raw_choice == '\x03' or choice == '': return 0
                
                if not choice.isdigit():
                    print(f"\n{RED}Invalid choice!{RESET}\n")
                    continue
                    
                numeric_choice = int(choice)
                if numeric_choice < 1 or numeric_choice > max_range:
                    print(f"\n{RED}Invalid choice!{RESET}\n")
                    continue
                    
                return numeric_choice

        except (EOFError, KeyboardInterrupt):
            print()
            return 0
