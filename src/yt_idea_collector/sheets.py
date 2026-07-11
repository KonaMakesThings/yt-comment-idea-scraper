from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import Baseline, Classification, Comment, Score, Video
from .retry import with_retry

IDEA_HEADERS = [
    "Review Status", "Creator Notes", "Opportunity Score", "Score Confidence", "Score Rationale",
    "Idea Summary", "Idea Type", "Inferred Game/Topic", "Source Video Title", "Video Link",
    "Comment Link", "Username", "Posted Time", "Raw Comment", "Comment Likes",
    "Classification Confidence", "Processed Time", "Comment ID",
]
PROCESSED_HEADERS = ["Comment ID", "YouTube Updated Time", "Classification Outcome", "Idea Row ID"]
BASELINE_HEADERS = [
    "Video ID", "Title", "Published Time", "Topic", "Views (First 30d)", "Watch Minutes (First 30d)",
    "Average Viewed %", "Likes", "Comments", "Shares", "Subscribers Gained", "Refreshed Time",
]
RUN_HEADERS = ["Run Time", "Status", "Fetched", "Eligible", "Ideas", "Errors", "Dry Run", "Message"]


class SheetStore:
    def __init__(self, service: Any, spreadsheet_id: str):
        self.service = service
        self.id = spreadsheet_id

    def ensure_layout(self) -> None:
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties,protectedRanges)",
        ).execute())
        existing = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
        requests: list[dict[str, Any]] = []
        for title in ("Ideas", "_Processed", "_VideoBaseline", "_RunLog"):
            if title not in existing:
                requests.append({"addSheet": {"properties": {"title": title, "hidden": title.startswith("_")}}})
            elif title.startswith("_") and not existing[title].get("hidden"):
                requests.append({"updateSheetProperties": {"properties": {"sheetId": existing[title]["sheetId"], "hidden": True}, "fields": "hidden"}})
        if requests:
            with_retry(lambda: self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.id, body={"requests": requests},
            ).execute())
        # Refresh IDs after additions, then give hidden implementation tabs a
        # warning-only protection so accidental edits are discouraged but recoverable.
        meta = with_retry(lambda: self.service.spreadsheets().get(
            spreadsheetId=self.id, fields="sheets(properties,protectedRanges)",
        ).execute())
        protections = []
        for sheet in meta.get("sheets", []):
            props = sheet["properties"]
            if props["title"].startswith("_") and not sheet.get("protectedRanges"):
                protections.append({"addProtectedRange": {"protectedRange": {
                    "range": {"sheetId": props["sheetId"]},
                    "description": "Managed by YouTube Comment Idea Collector",
                    "warningOnly": True,
                }}})
        if protections:
            with_retry(lambda: self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.id, body={"requests": protections},
            ).execute())
        for title, headers in (("Ideas", IDEA_HEADERS), ("_Processed", PROCESSED_HEADERS),
                               ("_VideoBaseline", BASELINE_HEADERS), ("_RunLog", RUN_HEADERS)):
            current = self._values(f"'{title}'!1:1")
            if not current:
                self._update(f"'{title}'!A1", [headers])
            elif current[0][:len(headers)] != headers:
                raise ValueError(f"Unexpected columns in {title}; refusing to overwrite user data")

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

    def processed(self) -> dict[str, tuple[str, str, str]]:
        rows = self._values("'_Processed'!A2:D")
        return {row[0]: tuple((row + ["", "", ""])[1:4]) for row in rows if row}

    def ideas(self) -> dict[str, tuple[int, list[str]]]:
        rows = self._values("'Ideas'!A2:R")
        result = {}
        for index, row in enumerate(rows, start=2):
            padded = row + [""] * (len(IDEA_HEADERS) - len(row))
            if padded[17]:
                result[padded[17]] = (index, padded)
        return result

    def write_result(self, comment: Comment, result: Classification, score: Score | None,
                     video: Video, existing_idea: tuple[int, list[str]] | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        idea_row_id = str(existing_idea[0]) if existing_idea else ""
        if result.is_idea:
            old = existing_idea[1] if existing_idea else [""] * len(IDEA_HEADERS)
            row = [
                old[0] or "New", old[1], score.value if score else "", score.confidence if score else "",
                score.rationale if score else "", result.summary, result.idea_type, result.topic, video.title,
                f"https://www.youtube.com/watch?v={video.id}",
                f"https://www.youtube.com/watch?v={video.id}&lc={comment.id}", comment.author_name,
                comment.published_at.isoformat(), comment.text, comment.like_count, result.confidence, now, comment.id,
            ]
            if existing_idea:
                self._update(f"'Ideas'!A{existing_idea[0]}", [row])
            else:
                self._append("'Ideas'!A:R", [row])
                idea_row_id = "created"
        elif existing_idea:
            old = existing_idea[1]
            old[0] = "No longer qualifies"
            old[16] = now
            self._update(f"'Ideas'!A{existing_idea[0]}", [old])
        state = [comment.id, comment.updated_at.isoformat(), "idea" if result.is_idea else "not_idea", idea_row_id]
        processed = self.processed()
        if comment.id in processed:
            rows = self._values("'_Processed'!A2:A")
            row_number = next(i for i, row in enumerate(rows, 2) if row and row[0] == comment.id)
            self._update(f"'_Processed'!A{row_number}", [state])
        else:
            self._append("'_Processed'!A:D", [state])

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
