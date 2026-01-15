"""Vulture whitelist for FastAPI endpoints wired through decorators."""

from app.api.v1 import (
    answers,
    assignments,
    chat,
    config,
    datasets,
    ground_truths,
    schemas,
    search,
    stats,
    tags,
)

assignments.self_serve_assignments
assignments.list_my_assignments
assignments.update_item
assignments.assign_item
assignments.duplicate_assignment_item

answers.generate_answer
chat.chat
config.get_frontend_config
datasets.list_datasets
datasets.get_curation_instructions
datasets.put_curation_instructions
datasets.delete_dataset

ground_truths.import_bulk
ground_truths.list_all_ground_truths
ground_truths.list_ground_truths
ground_truths.get_ground_truth
ground_truths.update_ground_truth
ground_truths.delete_item
ground_truths.recompute_computed_tags

tags.get_tags_schema
tags.get_tags
tags.post_tags
tags.delete_tags
schemas.list_schemas
schemas.get_schema
search.search
stats.get_stats
