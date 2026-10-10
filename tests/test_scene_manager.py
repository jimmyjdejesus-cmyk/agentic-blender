import pytest
from agentic_blender.cad import scene_manager

def test_scene_manager_module_exports():
    assert hasattr(scene_manager, "ensure_collection")
    assert hasattr(scene_manager, "move_object_to_collection")
    assert hasattr(scene_manager, "organize_into_collections")
    assert hasattr(scene_manager, "list_collections")
    assert hasattr(scene_manager, "set_collection_visibility")
    assert hasattr(scene_manager, "isolate_collection")
    assert hasattr(scene_manager, "clear_all_collections")
    assert hasattr(scene_manager, "list_libraries")
    assert hasattr(scene_manager, "link_or_append_library")
    assert hasattr(scene_manager, "create_pbr_material")
    assert hasattr(scene_manager, "assign_material")
    assert hasattr(scene_manager, "setup_studio_scene")
