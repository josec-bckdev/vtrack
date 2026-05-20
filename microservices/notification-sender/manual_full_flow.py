# test_full_flow.py
import sys
import os
sys.path.insert(0, os.path.expanduser('~/PythonCode/vtrack/shared-package/src'))

from shared.message_queue import MessageQueue
from datetime import datetime
import time

# 1. Create message queue connection
queue = MessageQueue(redis_url='redis://localhost:6379/0')

# 2. Push an alert (using the correct method signature)
success = queue.push_alert(
    ruta=101,
    latitude=4.7110,
    longitude=-74.0059,
    alert_type="GEOFENCE_ENTRY",
    area_name="Boyaca",
    severity="WARNING"
)

if success:
    print("✅ Alert pushed to Redis")
    print("📊 Alert queue length:", queue.get_queue_length('alert_queue'))
else:
    print("❌ Failed to push alert")

# 3. Run your notification consumer in another terminal:
# python main.py