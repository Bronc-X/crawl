from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .database import connect, init_db
from .schemas import (
    Channel,
    ChannelListing,
    ChannelListingUpsert,
    ChannelSetting,
    ChannelSettingUpsert,
    ListingState,
    Product,
    ProductCreate,
    ProductUpdate,
    PublishAction,
    PublishTask,
    PublishTaskStatus,
    RealSendBridgeRequest,
    RealSendJob,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ListingRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        init_db(db_path)

    def _serialize_media(self, media: list[Any]) -> str:
        payload: list[Any] = []
        for asset in media:
            if hasattr(asset, "model_dump"):
                payload.append(asset.model_dump(mode="json"))
            else:
                payload.append(asset)
        return json.dumps(payload)

    def _row_to_product(self, row: Any) -> Product:
        return Product(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            category=row["category"],
            price=row["price"],
            currency=row["currency"],
            status=row["status"],
            attributes=json.loads(row["attributes_json"]),
            media=json.loads(row["media_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _empty_channel_setting(self, channel: Channel) -> ChannelSetting:
        return ChannelSetting(
            channel=channel,
            default_category=None,
            default_currency=None,
            default_attributes={},
            updated_at="",
        )

    def _row_to_listing(self, row: Any) -> ChannelListing:
        return ChannelListing(
            id=row["id"],
            product_id=row["product_id"],
            channel=row["channel"],
            state=row["state"],
            external_id=row["external_id"],
            title_override=row["title_override"],
            description_override=row["description_override"],
            price_override=row["price_override"],
            attributes_override=json.loads(row["attributes_override_json"]),
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_task(self, row: Any) -> PublishTask:
        return PublishTask(
            id=row["id"],
            product_id=row["product_id"],
            channel=row["channel"],
            action=row["action"],
            status=row["status"],
            adapter=row["adapter"],
            listing_state=row["listing_state"],
            external_id=row["external_id"],
            result=json.loads(row["result_json"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_channel_setting(self, row: Any) -> ChannelSetting:
        return ChannelSetting(
            channel=row["channel"],
            default_category=row["default_category"],
            default_currency=row["default_currency"],
            default_attributes=json.loads(row["default_attributes_json"]),
            updated_at=row["updated_at"],
        )

    def _row_to_real_send_job(self, row: Any) -> RealSendJob:
        return RealSendJob(
            id=row["id"],
            channel=row["channel"],
            action=row["action"],
            status=row["status"],
            external_id=row["external_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
        )

    def create_product(self, payload: ProductCreate) -> Product:
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO products (
                    title, description, category, price, currency, status,
                    attributes_json, media_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.title,
                    payload.description,
                    payload.category,
                    payload.price,
                    payload.currency,
                    payload.status.value,
                    json.dumps(payload.attributes),
                    self._serialize_media(payload.media),
                    timestamp,
                    timestamp,
                ),
            )
            product_id = int(cursor.lastrowid)
        return self.get_product(product_id)

    def list_products(self) -> list[Product]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_product(row) for row in rows]

    def get_product(self, product_id: int) -> Product:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Product {product_id} not found")
        return self._row_to_product(row)

    def update_product(self, product_id: int, payload: ProductUpdate) -> Product:
        current = self.get_product(product_id)
        updated = current.model_copy(update=payload.model_dump(exclude_unset=True))
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE products
                SET title = ?, description = ?, category = ?, price = ?, currency = ?,
                    status = ?, attributes_json = ?, media_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.title,
                    updated.description,
                    updated.category,
                    updated.price,
                    updated.currency,
                    updated.status.value,
                    json.dumps(updated.attributes),
                    self._serialize_media(updated.media),
                    timestamp,
                    product_id,
                ),
            )
        return self.get_product(product_id)

    def upsert_channel_listing(
        self, product_id: int, payload: ChannelListingUpsert
    ) -> ChannelListing:
        self.get_product(product_id)
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT id FROM channel_listings
                WHERE product_id = ? AND channel = ?
                """,
                (product_id, payload.channel.value),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO channel_listings (
                        product_id, channel, state, external_id, title_override,
                        description_override, price_override, attributes_override_json,
                        last_error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        payload.channel.value,
                        ListingState.draft.value,
                        None,
                        payload.title_override,
                        payload.description_override,
                        payload.price_override,
                        json.dumps(payload.attributes_override),
                        None,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE channel_listings
                    SET title_override = ?, description_override = ?, price_override = ?,
                        attributes_override_json = ?, updated_at = ?
                    WHERE product_id = ? AND channel = ?
                    """,
                    (
                        payload.title_override,
                        payload.description_override,
                        payload.price_override,
                        json.dumps(payload.attributes_override),
                        timestamp,
                        product_id,
                        payload.channel.value,
                    ),
                )

        return self.get_channel_listing(product_id, payload.channel)

    def get_channel_listing(self, product_id: int, channel: Channel) -> ChannelListing:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM channel_listings
                WHERE product_id = ? AND channel = ?
                """,
                (product_id, channel.value),
            ).fetchone()
        if row is None:
            raise KeyError(f"Listing for product {product_id} channel {channel} not found")
        return self._row_to_listing(row)

    def list_channel_listings(self, product_id: int) -> list[ChannelListing]:
        self.get_product(product_id)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM channel_listings
                WHERE product_id = ?
                ORDER BY channel
                """,
                (product_id,),
            ).fetchall()
        return [self._row_to_listing(row) for row in rows]

    def get_channel_setting(self, channel: Channel) -> ChannelSetting:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM channel_settings WHERE channel = ?",
                (channel.value,),
            ).fetchone()
        if row is None:
            return self._empty_channel_setting(channel)
        return self._row_to_channel_setting(row)

    def list_channel_settings(self) -> list[ChannelSetting]:
        return [self.get_channel_setting(channel) for channel in Channel]

    def upsert_channel_setting(
        self, channel: Channel, payload: ChannelSettingUpsert
    ) -> ChannelSetting:
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO channel_settings (
                    channel, default_category, default_currency,
                    default_attributes_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(channel) DO UPDATE SET
                    default_category = excluded.default_category,
                    default_currency = excluded.default_currency,
                    default_attributes_json = excluded.default_attributes_json,
                    updated_at = excluded.updated_at
                """,
                (
                    channel.value,
                    payload.default_category,
                    payload.default_currency,
                    json.dumps(payload.default_attributes),
                    timestamp,
                ),
            )
        return self.get_channel_setting(channel)

    def save_publish_task(
        self,
        *,
        product_id: int,
        channel: Channel,
        action: PublishAction,
        status: PublishTaskStatus,
        adapter: str,
        listing_state: ListingState,
        external_id: str | None,
        result: dict[str, Any],
        error_message: str | None,
    ) -> PublishTask:
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO publish_tasks (
                    product_id, channel, action, status, adapter, listing_state,
                    external_id, result_json, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    channel.value,
                    action.value,
                    status.value,
                    adapter,
                    listing_state.value,
                    external_id,
                    json.dumps(result),
                    error_message,
                    timestamp,
                    timestamp,
                ),
            )
            task_id = int(cursor.lastrowid)
        return self.get_publish_task(task_id)

    def get_publish_task(self, task_id: int) -> PublishTask:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM publish_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Publish task {task_id} not found")
        return self._row_to_task(row)

    def list_publish_tasks(self) -> list[PublishTask]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM publish_tasks ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def update_listing_state(
        self,
        *,
        product_id: int,
        channel: Channel,
        state: ListingState,
        external_id: str | None,
        last_error: str | None,
    ) -> ChannelListing:
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT id FROM channel_listings
                WHERE product_id = ? AND channel = ?
                """,
                (product_id, channel.value),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO channel_listings (
                        product_id, channel, state, external_id, title_override,
                        description_override, price_override, attributes_override_json,
                        last_error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        channel.value,
                        state.value,
                        external_id,
                        None,
                        None,
                        None,
                        "{}",
                        last_error,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE channel_listings
                    SET state = ?, external_id = ?, last_error = ?, updated_at = ?
                    WHERE product_id = ? AND channel = ?
                    """,
                    (
                        state.value,
                        external_id,
                        last_error,
                        timestamp,
                        product_id,
                        channel.value,
                    ),
                )
        return self.get_channel_listing(product_id, channel)

    def save_real_send_job(
        self, payload: RealSendBridgeRequest, status: str = "awaiting_human_confirm"
    ) -> RealSendJob:
        timestamp = now_iso()
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO real_send_jobs (
                    channel, action, status, external_id, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.channel.value,
                    payload.action.value,
                    status,
                    "",
                    json.dumps(payload.payload),
                    timestamp,
                ),
            )
            job_id = int(cursor.lastrowid)
            external_id = f"local-real-send-{payload.channel.value}-{job_id}"
            conn.execute(
                "UPDATE real_send_jobs SET external_id = ? WHERE id = ?",
                (external_id, job_id),
            )
        return self.get_real_send_job(job_id)

    def get_real_send_job(self, job_id: int) -> RealSendJob:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM real_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Real-send job {job_id} not found")
        return self._row_to_real_send_job(row)

    def list_real_send_jobs(self) -> list[RealSendJob]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM real_send_jobs ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_real_send_job(row) for row in rows]
