from __future__ import annotations

from pathlib import Path

from core.schemas.macro import MacroDataQuality, MacroObservation, MacroSeriesDefinition
from pipelines.data_mart.storage.db import connect, init_db
from pipelines.macro.providers.base import MacroDataProvider, MacroProviderResult


class DataMartMacroProvider(MacroDataProvider):
    provider_name = "data_mart"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def is_available(self) -> bool:
        try:
            init_db(self.db_path)
            return True
        except Exception:  # noqa: BLE001
            return False

    def supports(self, definition: MacroSeriesDefinition) -> bool:
        return bool(definition.enabled)

    def fetch_series(
        self,
        definition: MacroSeriesDefinition,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MacroProviderResult:
        if not self.supports(definition):
            return MacroProviderResult(
                provider=self.provider_name,
                observations=[],
                data_quality=MacroDataQuality(
                    status="unavailable",
                    provider=self.provider_name,
                    missing_series=[definition.series_id],
                    errors=[f"series disabled: {definition.series_id}"],
                ),
            )
        try:
            init_db(self.db_path)
            clauses = ["o.series_id=?"]
            params: list[str] = [definition.provider_series_id]
            if start_date:
                clauses.append("o.date>=?")
                params.append(start_date)
            if end_date:
                clauses.append("o.date<=?")
                params.append(end_date)
            where = " AND ".join(clauses)
            with connect(self.db_path) as conn:
                # WHERE clauses are fixed templates with bound values.
                query = "\n".join(
                    [
                        """
                        SELECT o.date, o.value, o.source, o.collected_at
                        FROM macro_observations o
                        WHERE """,
                        where,
                        """
                        ORDER BY o.date ASC
                        """,
                    ]
                )
                rows = conn.execute(query, tuple(params)).fetchall()
        except Exception as exc:  # noqa: BLE001
            return MacroProviderResult(
                provider=self.provider_name,
                observations=[],
                data_quality=MacroDataQuality(
                    status="unavailable",
                    provider=self.provider_name,
                    missing_series=[definition.series_id],
                    errors=[f"data_mart_error:{exc}"],
                ),
            )

        observations = [
            MacroObservation(
                date=str(row["date"] or ""),
                value=float(row["value"]) if row["value"] is not None else None,
                raw_value=float(row["value"]) if row["value"] is not None else None,
                source=str(row["source"] or self.provider_name),
                metadata={"collected_at": row["collected_at"]},
            )
            for row in rows
            if row["date"]
        ]
        if not observations:
            return MacroProviderResult(
                provider=self.provider_name,
                observations=[],
                data_quality=MacroDataQuality(
                    status="unavailable",
                    provider=self.provider_name,
                    missing_series=[definition.series_id],
                    notes=[f"no cached observations for {definition.series_id}"],
                ),
            )
        return MacroProviderResult(
            provider=self.provider_name,
            observations=observations,
            data_quality=MacroDataQuality(
                status="ok",
                provider=self.provider_name,
                last_updated=observations[-1].metadata.get("collected_at") or observations[-1].date,
            ),
        )
