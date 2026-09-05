from processing.event_clusterer import cluster_contents
from sheets.contents_repository import get_unclustered_contents
from sheets.events_repository import (
    append_content_events,
    append_events,
    get_all_events,
    get_clustered_content_ids,
    update_events_last_seen,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def run_event_clustering() -> None:
    clustered_ids = get_clustered_content_ids()
    contents = get_unclustered_contents(clustered_ids)
    existing_events = get_all_events()

    logger.info(f"Unclustered contents: {len(contents)}, existing events: {len(existing_events)}")

    if not contents:
        logger.info("Nothing to cluster")
        return

    new_events, content_event_rows, last_seen_updates = cluster_contents(contents, existing_events)

    append_events(new_events)
    append_content_events(content_event_rows)
    update_events_last_seen(last_seen_updates)

    logger.info(
        f"Run finished: {len(new_events)} new events created, "
        f"{len(content_event_rows)} contents assigned, {len(last_seen_updates)} existing events updated"
    )


if __name__ == "__main__":
    run_event_clustering()
