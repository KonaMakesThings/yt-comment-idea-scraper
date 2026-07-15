from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .models import Baseline, Classification, Comment, Score, Video
from .duplicates import duplicate_group
from .retry import with_retry

LEGACY_IDEA_HEADERS = [
    "Review Status", "Creator Notes", "Opportunity Score", "Score Confidence", "Score Rationale",
    "Idea Summary", "Idea Type", "Inferred Game/Topic", "Source Video Title", "Video Link",
    "Comment Link", "Username", "Posted Time", "Raw Comment", "Comment Likes",
    "Classification Confidence", "Processed Time", "Comment ID",
]
LEGACY_QUEUE_HEADERS = [
    "Review Status", "Opportunity Score", "Idea Summary", "Inferred Game/Topic",
    "Source Video Title", "Comment Link", "Posted Time", "Creator Notes",
    "Score Confidence", "Score Rationale", "Idea Type", "Video Link", "Username",
    "Raw Comment", "Comment Likes", "Classification Confidence", "Processed Time", "Comment ID",
]
IDEA_HEADERS = [
    "Review Status", "Opportunity Score", "Idea Summary", "Original Comment",
    "Inferred Game/Topic", "Source Video Title", "Comment Link", "Posted Time", "Creator Notes",
    "Duplicate Group", "Score Confidence", "Score Rationale", "Idea Type", "Video Link", "Username",
    "Comment Likes", "Classification Confidence", "Processed Time", "Comment ID",
]
QUEUE_SHEET = "Review Queue"
PROCESSED_HEADERS = [
    "Comment ID", "YouTube Updated Time", "Classification Outcome", "Idea Row ID", "Classifier Version",
]
BASELINE_HEADERS = [
    "Video ID", "Title", "Published Time", "Topic", "Views (First 30d)", "Watch Minutes (First 30d)",
    "Average Viewed %", "Likes", "Comments", "Shares", "Subscribers Gained", "Refreshed Time",
]
RUN_HEADERS = ["Run Time", "Status", "Fetched", "Eligible", "Ideas", "Errors", "Dry Run", "Message"]


class SheetStore:
    def __init__(self, service: Any, spreadsheet_id: str):
        self.service = service
        self.id = spreadsheet_id
        self._ideas_cache: dict[str, tuple[int, list[str]]] | None = None
        self._processed_cache: dict[str, tuple[int, tuple[str, str, str, str]]] | None = None

    def ensure_layout(self) -> None:
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties,protectedRanges)",
        ).execute())
        existing = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
        requests: list[dict[str, Any]] = []
        for title in (QUEUE_SHEET, "_Processed", "_VideoBaseline", "_RunLog"):
            if title not in existing:
                requests.append({"addSheet": {"properties": {"title": title, "hidden": title.startswith("_")}}})
            elif title.startswith("_") and not existing[title].get("hidden"):
                requests.append({"updateSheetProperties": {"properties": {"sheetId": existing[title]["sheetId"], "hidden": True}, "fields": "hidden"}})
        if requests:
            with_retry(lambda: self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.id, body={"requests": requests},
            ).execute())
        # Refresh IDs after additions, migrate the legacy Ideas tab once, then give hidden implementation tabs a
        # warning-only protection so accidental edits are discouraged but recoverable.
        self._migrate_legacy_ideas()
        self._migrate_queue_headers()
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties,protectedRanges)",
        ).execute())
        maintenance: list[dict[str, Any]] = []
        protections = []
        for sheet in meta.get("sheets", []):
            props = sheet["properties"]
            if props["title"] == "Ideas" and not props.get("hidden"):
                maintenance.append({"updateSheetProperties": {
                    "properties": {"sheetId": props["sheetId"], "hidden": True}, "fields": "hidden",
                }})
            if props["title"].startswith("_") and not sheet.get("protectedRanges"):
                protections.append({"addProtectedRange": {"protectedRange": {
                    "range": {"sheetId": props["sheetId"]},
                    "description": "Managed by YouTube Comment Idea Collector",
                    "warningOnly": True,
                }}})
        if maintenance or protections:
            with_retry(lambda: self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.id, body={"requests": maintenance + protections},
            ).execute())
        for title, headers in ((QUEUE_SHEET, IDEA_HEADERS), ("_Processed", PROCESSED_HEADERS),
                               ("_VideoBaseline", BASELINE_HEADERS), ("_RunLog", RUN_HEADERS)):
            self._ensure_headers(title, headers)
        self._format_review_queue()
        self._ideas_cache = None
        self._processed_cache = None

    def _migrate_legacy_ideas(self) -> None:
        """Copy the old wide Ideas table into the compact queue without deleting the backup."""
        queue = self._values(f"'{QUEUE_SHEET}'!A1:S")
        if len(queue) > 1:
            return
        try:
            legacy = self._values("'Ideas'!A1:R")
        except Exception:
            return
        if len(legacy) <= 1:
            return
        current_headers = legacy[0]
        if set(LEGACY_IDEA_HEADERS).issubset(set(current_headers)):
            positions = {name: current_headers.index(name) for name in LEGACY_IDEA_HEADERS}
        else:
            positions = {name: index for index, name in enumerate(LEGACY_IDEA_HEADERS)}
        migrated = [IDEA_HEADERS]
        for source in legacy[1:]:
            padded = source + [""] * len(LEGACY_IDEA_HEADERS)
            by_name = {name: padded[index] for name, index in positions.items()}
            by_name["Original Comment"] = by_name.get("Raw Comment", "")
            by_name["Duplicate Group"] = duplicate_group(
                by_name.get("Idea Summary", ""), by_name.get("Inferred Game/Topic", ""),
            )
            migrated.append([by_name.get(header, "") for header in IDEA_HEADERS])
        self._update(f"'{QUEUE_SHEET}'!A1", migrated)

    def _migrate_queue_headers(self) -> None:
        """Upgrade an existing Review Queue while preserving notes and raw comments."""
        queue = self._values(f"'{QUEUE_SHEET}'!A1:S")
        if not queue:
            return
        current_headers = queue[0]
        if current_headers[:len(IDEA_HEADERS)] == IDEA_HEADERS:
            return
        if not set(LEGACY_QUEUE_HEADERS).issubset(set(current_headers)):
            return
        positions = {name: current_headers.index(name) for name in LEGACY_QUEUE_HEADERS}
        migrated = [IDEA_HEADERS]
        for source in queue[1:]:
            padded = source + [""] * len(LEGACY_QUEUE_HEADERS)
            by_name = {name: padded[index] for name, index in positions.items()}
            by_name["Original Comment"] = by_name.get("Raw Comment", "")
            by_name["Duplicate Group"] = by_name.get("Duplicate Group") or duplicate_group(
                by_name.get("Idea Summary", ""), by_name.get("Inferred Game/Topic", ""),
            )
            migrated.append([by_name.get(header, "") for header in IDEA_HEADERS])
        self._update(f"'{QUEUE_SHEET}'!A1", migrated)

    def _format_review_queue(self) -> None:
        sheet_id = self._sheet_id(QUEUE_SHEET)
        widths = [110, 90, 360, 430, 190, 270, 150, 165, 250, 180]
        requests: list[dict[str, Any]] = [{
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "index": 0,
                               "gridProperties": {"frozenRowCount": 1}},
                "fields": "index,gridProperties.frozenRowCount",
            }
        }, {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": len(IDEA_HEADERS)},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.25, "green": 0.25, "blue": 0.27},
                    "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                   "bold": True},
                    "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                }},
                "fields": "userEnteredFormat",
            }
        }, {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": 10},
                "cell": {"userEnteredFormat": {"verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy",
            }
        }, {
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "rule": {"condition": {"type": "ONE_OF_LIST", "values": [
                    {"userEnteredValue": value} for value in ("New", "Keep", "Maybe", "Reject", "Duplicate", "Used")
                ]}, "strict": True, "showCustomUi": True},
            }
        }, {
            "setBasicFilter": {"filter": {"range": {"sheetId": sheet_id,
                                                       "startRowIndex": 0,
                                                       "startColumnIndex": 0,
                                                       "endColumnIndex": len(IDEA_HEADERS)}}}
        }, {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": 10, "endIndex": len(IDEA_HEADERS)},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser",
            }
        }, {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1},
                "properties": {"pixelSize": 78}, "fields": "pixelSize",
            }
        }]
        for index, width in enumerate(widths):
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": index, "endIndex": index + 1},
                "properties": {"pixelSize": width, "hiddenByUser": False},
                "fields": "pixelSize,hiddenByUser",
            }})
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties(sheetId,title),conditionalFormats)",
        ).execute())
        rules_exist = any(
            sheet.get("properties", {}).get("sheetId") == sheet_id and sheet.get("conditionalFormats")
            for sheet in meta.get("sheets", [])
        )
        if not rules_exist:
            status_colors = {
                "Keep": {"red": 0.86, "green": 0.95, "blue": 0.88},
                "Maybe": {"red": 1.0, "green": 0.95, "blue": 0.78},
                "Reject": {"red": 1.0, "green": 0.86, "blue": 0.86},
                "Duplicate": {"red": 0.91, "green": 0.87, "blue": 1.0},
                "Used": {"red": 0.84, "green": 0.92, "blue": 1.0},
            }
            for index, (status, color) in enumerate(status_colors.items()):
                requests.append({"addConditionalFormatRule": {"index": index, "rule": {
                    "ranges": [{"sheetId": sheet_id, "startRowIndex": 1,
                                "startColumnIndex": 0, "endColumnIndex": len(IDEA_HEADERS)}],
                    "booleanRule": {"condition": {"type": "CUSTOM_FORMULA",
                                                   "values": [{"userEnteredValue": f'=$A2="{status}"'}]},
                                    "format": {"backgroundColor": color}},
                }}})
        with_retry(lambda: self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.id, body={"requests": requests},
        ).execute())

    def _ensure_headers(self, title: str, headers: list[str]) -> None:
        """Restore the collector-owned header row without touching sheet data or formatting."""
        current = self._values(f"'{title}'!1:1")
        if not current or current[0][:len(headers)] != headers:
            # Row 1 is part of the collector's data interface. Updating A1 through
            # the final header cell preserves column widths, colors, filters, and
            # every data row while recovering from renamed or damaged headers.
            self._update(f"'{title}'!A1", [headers])

    def _values(self, range_: str) -> list[list[str]]:
        response = with_retry(lambda: self.service.spreadsheets().values().get(
            spreadsheetId=self.id, range=range_,
        ).execute())
        return response.get("values", [])

    def _update(self, range_: str, values: list[list[Any]]) -> None:
        with_retry(lambda: self.service.spreadsheets().values().update(
            spreadsheetId=self.id, range=range_, valueInputOption="RAW", body={"values": values},
        ).execute())

    def _append(self, range_: str, values: list[list[Any]]) -> None:
        with_retry(lambda: self.service.spreadsheets().values().append(
            spreadsheetId=self.id, range=range_, valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute())

    def _sheet_id(self, title: str) -> int:
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties(sheetId,title))",
        ).execute())
        for sheet in meta.get("sheets", []):
            properties = sheet["properties"]
            if properties["title"] == title:
                return properties["sheetId"]
        raise ValueError(f"Sheet tab not found: {title}")

    def _delete_row(self, title: str, row_number: int) -> None:
        sheet_id = self._sheet_id(title)
        with_retry(lambda: self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.id,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": sheet_id, "dimension": "ROWS",
                "startIndex": row_number - 1, "endIndex": row_number,
            }}}]},
        ).execute())

    def _processed_index(self) -> dict[str, tuple[int, tuple[str, str, str, str]]]:
        if self._processed_cache is None:
            rows = self._values("'_Processed'!A2:E")
            self._processed_cache = {
                row[0]: (index, tuple((row + ["", "", "", ""])[1:5]))
                for index, row in enumerate(rows, start=2) if row
            }
        return self._processed_cache

    def processed(self) -> dict[str, tuple[str, str, str, str]]:
        return {comment_id: state for comment_id, (_, state) in self._processed_index().items()}

    def ideas(self) -> dict[str, tuple[int, list[str]]]:
        if self._ideas_cache is not None:
            return self._ideas_cache
        rows = self._values(f"'{QUEUE_SHEET}'!A2:S")
        result: dict[str, tuple[int, list[str]]] = {}
        for index, row in enumerate(rows, start=2):
            padded = row + [""] * (len(IDEA_HEADERS) - len(row))
            comment_id = padded[IDEA_HEADERS.index("Comment ID")]
            if comment_id:
                result[comment_id] = (index, padded)
        self._ideas_cache = result
        return self._ideas_cache

    def write_result(self, comment: Comment, result: Classification, score: Score | None,
                     video: Video, existing_idea: tuple[int, list[str]] | None,
                     classifier_version: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        idea_row_id = str(existing_idea[0]) if existing_idea else ""
        if result.is_idea:
            old = existing_idea[1] if existing_idea else [""] * len(IDEA_HEADERS)
            row = [
                old[0] or "New", score.value if score else "", result.summary, comment.text, result.topic,
                video.title, f"https://www.youtube.com/watch?v={video.id}&lc={comment.id}",
                comment.published_at.isoformat(), old[8], old[9] or duplicate_group(result.summary, result.topic),
                score.confidence if score else "", score.rationale if score else "", result.idea_type,
                f"https://www.youtube.com/watch?v={video.id}", comment.author_name, comment.like_count,
                result.confidence, now, comment.id,
            ]
            if existing_idea:
                row_number = existing_idea[0]
                self._update(f"'{QUEUE_SHEET}'!A{row_number}", [row])
            else:
                current = self.ideas()
                row_number = max((entry[0] for entry in current.values()), default=1) + 1
                self._append(f"'{QUEUE_SHEET}'!A:S", [row])
                idea_row_id = str(row_number)
            self.ideas()[comment.id] = (row_number, row)
        elif existing_idea:
            # A stricter reclassification means this no longer belongs in the
            # visible review queue. Keep its ID in _Processed for deduplication,
            # but remove the stale visible row entirely.
            deleted_row = existing_idea[0]
            self._delete_row(QUEUE_SHEET, deleted_row)
            cache = self.ideas()
            cache.pop(comment.id, None)
            for key, (row_number, row) in list(cache.items()):
                if row_number > deleted_row:
                    cache[key] = (row_number - 1, row)
            idea_row_id = ""
        self._record_processed(comment, "idea" if result.is_idea else "not_idea", idea_row_id,
                               classifier_version)

    def mark_processed(self, comment: Comment, outcome: str, classifier_version: str = "",
                       idea_row_id: str = "") -> None:
        """Record a terminal outcome for a comment without adding it to the queue."""
        self._record_processed(comment, outcome, idea_row_id, classifier_version)

    def _record_processed(self, comment: Comment, outcome: str, idea_row_id: str,
                          classifier_version: str) -> None:
        state = [comment.id, comment.updated_at.isoformat(), outcome, idea_row_id, classifier_version]
        processed = self._processed_index()
        if comment.id in processed:
            row_number = processed[comment.id][0]
            self._update(f"'_Processed'!A{row_number}", [state])
        else:
            row_number = max((entry[0] for entry in processed.values()), default=1) + 1
            self._append("'_Processed'!A:E", [state])
        processed[comment.id] = (row_number, tuple(state[1:5]))

    def baselines(self, *, max_age_days: int = 7) -> list[Baseline]:
        rows = self._values("'_VideoBaseline'!A2:L")
        if not rows:
            return []
        try:
            refreshed = max(datetime.fromisoformat(row[11]) for row in rows if len(row) > 11 and row[11])
            if refreshed < datetime.now(timezone.utc) - timedelta(days=max_age_days):
                return []
            result = []
            for row in rows:
                padded = row + [""] * (12 - len(row))
                video = Video(padded[0], padded[1], "", datetime.fromisoformat(padded[2]), 0, "none")
                result.append(Baseline(video, padded[3], *(float(value or 0) for value in padded[4:11])))
            return result
        except (ValueError, TypeError):
            return []

    def write_baselines(self, rows: list[Baseline]) -> None:
        values = [[
            r.video.id, r.video.title, r.video.published_at.isoformat(), r.topic, r.views, r.watch_minutes,
            r.average_view_percentage, r.likes, r.comments, r.shares, r.subscribers_gained,
            datetime.now(timezone.utc).isoformat(),
        ] for r in rows]
        with_retry(lambda: self.service.spreadsheets().values().clear(
            spreadsheetId=self.id, range="'_VideoBaseline'!A2:L", body={},
        ).execute())
        if values:
            self._update("'_VideoBaseline'!A2", values)

    def log_run(self, status: str, fetched: int, eligible: int, ideas: int, errors: int,
                dry_run: bool, message: str = "") -> None:
        self._append("'_RunLog'!A:H", [[datetime.now(timezone.utc).isoformat(), status, fetched,
                                         eligible, ideas, errors, dry_run, message[:500]]])
