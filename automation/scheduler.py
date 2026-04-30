import subprocess
import time


try:
    while True:
        print("Starting job run...")

        subprocess.run(["python3", "automation/runner.py"])

        print("Run completed. Sleeping for 24 hours...\n")

        time.sleep(86400)
except KeyboardInterrupt:
    print("Stopped manually")
