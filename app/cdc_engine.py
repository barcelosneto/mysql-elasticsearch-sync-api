import time
import json
import logging
from datetime import datetime
from elasticsearch import helpers
from app.config import settings
from app.database import SessionLocal, es_client
from app.models import CDCOutboxEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (CDC Engine) %(message)s")
logger = logging.getLogger("cdc_engine")

class CDCSyncEngine:
    """
    High-Performance Change Data Capture (CDC) Worker.
    Polls the Outbox event stream and propagates inserts, updates, and deletes
    to Elasticsearch using Bulk API with sub-second synchronization.
    """

    def __init__(self):
        self.batch_size = settings.CDC_BATCH_SIZE
        self.index_name = settings.ES_INDEX_NAME

    def process_pending_events(self) -> int:
        db = SessionLocal()
        try:
            # 1. Fetch pending CDC events with row locking or batch slice
            events = (
                db.query(CDCOutboxEvent)
                .filter(CDCOutboxEvent.status == 'PENDING')
                .order_by(CDCOutboxEvent.id.asc())
                .limit(self.batch_size)
                .all()
            )

            if not events:
                return 0

            start_time = time.perf_counter()
            actions = []
            events_to_update = []

            for event in events:
                payload = event.payload
                if isinstance(payload, str):
                    payload = json.loads(payload)

                doc_id = str(event.aggregate_id)

                if event.event_type in ('INSERT', 'UPDATE'):
                    actions.append({
                        "_op_type": "index",
                        "_index": self.index_name,
                        "_id": doc_id,
                        "_source": payload
                    })
                elif event.event_type == 'DELETE':
                    actions.append({
                        "_op_type": "delete",
                        "_index": self.index_name,
                        "_id": doc_id
                    })

                events_to_update.append(event)

            # 2. Bulk send to Elasticsearch
            if actions:
                success_count, failed = helpers.bulk(es_client, actions, raise_on_error=False, ignore_status=[404])
                duration_ms = (time.perf_counter() - start_time) * 1000

                now = datetime.utcnow()
                for ev in events_to_update:
                    ev.status = 'PROCESSED'
                    ev.processed_at = now

                db.commit()
                logger.info(f"Synchronized {len(actions)} CDC events to Elasticsearch in {duration_ms:.2f}ms (Success: {success_count})")
                return len(actions)

        except Exception as e:
            db.rollback()
            logger.error(f"Error in CDC sync cycle: {e}")
            return 0
        finally:
            db.close()

    def run_continuous_loop(self):
        logger.info(f"Starting CDC Sync Engine with poll interval {settings.CDC_POLL_INTERVAL_MS}ms...")
        while True:
            processed = self.process_pending_events()
            if processed == 0:
                time.sleep(settings.CDC_POLL_INTERVAL_MS / 1000.0)

if __name__ == "__main__":
    engine = CDCSyncEngine()
    engine.run_continuous_loop()
