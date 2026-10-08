"""
Headless Agentic Blender Server Runner.
Keeps Blender alive as a background execution engine on http://127.0.0.1:9876.
Processes queued agent commands continuously.
"""

import time
import sys

try:
    import bpy
    import agentic_blender
except ImportError:
    print("Error: Could not import bpy or agentic_blender.")
    sys.exit(1)

print("\n" + "="*60)
print("  Agentic Blender Background Server is ONLINE")
print("  Listening for agent commands on http://127.0.0.1:9876")
print("="*60 + "\n")

try:
    while True:
        # Pump queued agent tasks
        agentic_blender.process_tasks_timer()
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Shutting down Agentic Blender Server...")
