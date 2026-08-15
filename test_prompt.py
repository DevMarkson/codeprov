import time

print("Starting deployment / installation simulation...")
time.sleep(1)
print("Step 1: Analyzing packages... Done.")
time.sleep(1)

# Interactive terminal prompt
answer = input("Dangerous action detected: Do you want to continue? [y/n]: ")

print(f"\nTerminal received answer: '{answer.strip()}'")
if answer.strip().lower() in ['y', 'yes', '1']:
    print("Action confirmed! Running tasks successfully.")
else:
    print("Action aborted by user.")
