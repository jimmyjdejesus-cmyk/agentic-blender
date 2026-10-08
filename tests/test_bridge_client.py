import pytest
from agentic_blender.bridge.client import BlenderBridgeClient

def test_bridge_client_init():
    client = BlenderBridgeClient(host="127.0.0.1", port=9876)
    assert client.base_url == "http://127.0.0.1:9876"

def test_bridge_client_offline_handling():
    # Test non-existent port to verify graceful failure
    client = BlenderBridgeClient(host="127.0.0.1", port=65432)
    assert client.is_online(timeout=0.2) is False
