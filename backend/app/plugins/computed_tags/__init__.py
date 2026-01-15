"""Computed Tags Plugins.

This package contains computed tag plugin implementations.
Plugins are automatically discovered from modules in this package.

To create a new plugin:
    1. Create a new module in this package (e.g., my_plugin.py)
    2. Define a class that inherits from ComputedTagPlugin
    3. Implement the tag_key property and compute method
    4. The plugin will be automatically registered

Example:
    from app.plugins.base import ComputedTagPlugin
    from app.domain.models import GroundTruthItem

    class MyPlugin(ComputedTagPlugin):
        @property
        def tag_key(self) -> str:
            return "my_group:my_value"

        def compute(self, doc: GroundTruthItem) -> bool:
            return some_condition(doc)
"""
