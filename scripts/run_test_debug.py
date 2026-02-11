#!/usr/bin/env python
"""
Debug tool for running tests with detailed output.
Usage: python run_test_debug.py [test_name]
"""

import subprocess
import sys
from pathlib import Path

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def run_command(cmd, description):
    """Run a command and display output."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}▶ {description}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}$ {' '.join(cmd)}{Colors.ENDC}\n")
    result = subprocess.run(cmd)
    return result.returncode

def main():
    venv_python = ".venv/bin/python"
    cwd = Path(__file__).parent
    
    # Change to workspace directory
    import os
    os.chdir(cwd)
    
    commands = {
        "1": {
            "desc": "MessageQueue Tests (with output)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_message_queue.py", "-v", "-s", "--tb=short"]
        },
        "2": {
            "desc": "LocationAlerts Tests (with output)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_location_alerts.py", "-v", "-s", "--tb=short"]
        },
        "3": {
            "desc": "AlertConsumer Tests (with output)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_alert_consumer.py", "-v", "-s", "--tb=short"]
        },
        "4": {
            "desc": "Integration Tests (with output)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_microservices_integration.py", "-v", "-s", "--tb=short"]
        },
        "5": {
            "desc": "All Microservices Tests",
            "cmd": [venv_python, "-m", "pytest", 
                    "app/tests/test_message_queue.py",
                    "app/tests/test_location_alerts.py",
                    "app/tests/test_alert_consumer.py",
                    "app/tests/test_microservices_integration.py",
                    "-v", "-s"]
        },
        "6": {
            "desc": "Run with Debugger (stops on failure)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_message_queue.py", "--pdb", "-x"]
        },
        "7": {
            "desc": "Show Fixture Setup/Teardown",
            "cmd": [venv_python, "-m", "pytest", "app/tests/test_message_queue.py::TestMessageQueueInitialization", "--setup-show", "-v"]
        },
        "8": {
            "desc": "Show Test Performance (slowest 10)",
            "cmd": [venv_python, "-m", "pytest", "app/tests/", "--durations=10"]
        }
    }
    
    print(f"\n{Colors.BOLD}{Colors.OKGREEN}=" * 60)
    print("VTrack Test Debugger".center(60))
    print("=" * 60 + Colors.ENDC)
    
    print(f"\n{Colors.BOLD}Available Debug Options:{Colors.ENDC}\n")
    
    for key, info in commands.items():
        print(f"{Colors.OKBLUE}{key}.{Colors.ENDC} {info['desc']}")
    
    print(f"\n{Colors.WARNING}Select option (1-8) or 'q' to quit: {Colors.ENDC}", end="")
    
    choice = input().strip()
    
    if choice.lower() == 'q':
        print("Exiting...")
        return 0
    
    if choice not in commands:
        print(f"{Colors.FAIL}Invalid choice{Colors.ENDC}")
        return 1
    
    cmd = commands[choice]["cmd"]
    desc = commands[choice]["desc"]
    
    return run_command(cmd, desc)

if __name__ == "__main__":
    sys.exit(main())
