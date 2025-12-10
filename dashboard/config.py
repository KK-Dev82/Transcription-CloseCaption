"""
Dashboard Configuration
"""
import os
from typing import Dict

# Server configurations
SERVERS: Dict[str, Dict[str, str]] = {
    "4000-ada": {
        "name": "4000-ada",
        "api_url": os.getenv("SERVER_4000ADA_URL", "http://87.197.119.40:40112"),
        "ssh": os.getenv("SERVER_4000ADA_SSH", "4000-ada"),
        "color": "#0071e3",  # Apple Blue
    },
    "5080": {
        "name": "5080",
        "api_url": os.getenv("SERVER_5080_URL", "http://213.144.200.206:15267"),
        "ssh": os.getenv("SERVER_5080_SSH", "5080"),
        "color": "#34c759",  # Apple Green
    },
}

