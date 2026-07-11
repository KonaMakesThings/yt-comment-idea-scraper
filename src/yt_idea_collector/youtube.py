from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .models import Baseline, Comment, Video
from .retry import with_retry


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_duration(value: str) -> int:
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTubeClient:
    def __init__(self, data_api: Any, analytics_api: Any, channel_id: str):
        self.data = data_api
        self.analytics = analytics_api
        self.channel_id = channel_id

    def list_comments(self) -> list[Comment]:
        comments: list[Comment] = []
        token: str | None = None
        while True:
            response = with_retry(lambda: self.data.commentThreads().list(
                part="snippet,replies",
                allThreadsRelatedToChannelId=self.channel_id,
                maxResults=100,
                order="time",
                textFormat="plainText",
                pageToken=token,
            ).execute())
            for thread in response.get("items", []):
                snippet = thread["snippet"]
                top = snippet["topLevelComment"]
                comments.append(self._comment(top, None))
                embedded = thread.get("replies", {}).get("comments", [])
                total = int(snippet.get("totalReplyCount", 0))
                replies = embedded
                if total > len(embedded):
                    replies = self._all_replies(top["id"])
                comments.extend(self._comment(reply, top["id"]) for reply in replies)
            token = response.get("nextPageToken")
            if not token:
                break
        return comments

    def _all_replies(self, parent_id: str) -> list[dict[str, Any]]:
        replies: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            response = with_retry(lambda: self.data.comments().list(
                part="snippet", parentId=parent_id, maxResults=100,
                textFormat="plainText", pageToken=token,
            ).execute())
            replies.extend(response.get("items", []))
            token = response.get("nextPageToken")
            if not token:
                return replies

    @staticmethod
    def _comment(resource: dict[str, Any], parent_id: str | None) -> Comment:
        snippet = resource["snippet"]
        author_channel = snippet.get("authorChannelId", {}).get("value")
        return Comment(
            id=resource["id"], video_id=snippet.get("videoId", ""), parent_id=parent_id,
            author_name=snippet.get("authorDisplayName", "Unknown"),
            author_channel_id=author_channel, text=snippet.get("textOriginal", ""),
            published_at=parse_datetime(snippet["publishedAt"]),
            updated_at=parse_datetime(snippet.get("updatedAt", snippet["publishedAt"])),
            like_count=int(snippet.get("likeCount", 0)),
        )

    def videos(self, video_ids: list[str]) -> dict[str, Video]:
        result: dict[str, Video] = {}
        for start in range(0, len(video_ids), 50):
            ids = video_ids[start:start + 50]
            response = with_retry(lambda: self.data.videos().list(
                part="snippet,contentDetails", id=",".join(ids), maxResults=50,
            ).execute())
            for item in response.get("items", []):
                snippet = item["snippet"]
                result[item["id"]] = Video(
                    id=item["id"], title=snippet["title"],
                    description=snippet.get("description", ""),
                    published_at=parse_datetime(snippet["publishedAt"]),
                    duration_seconds=parse_duration(item["contentDetails"]["duration"]),
                    live_broadcast_content=snippet.get("liveBroadcastContent", "none"),
                )
        return result

    def recent_uploads(self, *, months: int = 24) -> list[Video]:
        channel = with_retry(lambda: self.data.channels().list(
            part="contentDetails", id=self.channel_id,
        ).execute())
        uploads = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        ids: list[str] = []
        token: str | None = None
        stop = False
        while not stop:
            response = with_retry(lambda: self.data.playlistItems().list(
                part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token,
            ).execute())
            for item in response.get("items", []):
                published = parse_datetime(item["contentDetails"]["videoPublishedAt"])
                if published < cutoff:
                    stop = True
                    break
                ids.append(item["contentDetails"]["videoId"])
            token = response.get("nextPageToken")
            if stop or not token:
                break
        videos = self.videos(ids)
        # The Data API has no explicit isShort flag. <=3 minutes is the safest public-API heuristic.
        mature_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        return [v for v in videos.values() if v.duration_seconds > 180 and
                v.live_broadcast_content == "none" and v.published_at <= mature_cutoff]

    def analytics_baseline(self, video: Video, topic: str) -> Baseline:
        start = video.published_at.date()
        end = min(start + timedelta(days=29), datetime.now(timezone.utc).date() - timedelta(days=1))
        if end < start:
            values = [0.0] * 7
        else:
            response = with_retry(lambda: self.analytics.reports().query(
                ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                metrics=("views,estimatedMinutesWatched,averageViewPercentage,likes,comments,"
                         "shares,subscribersGained"), filters=f"video=={video.id}",
            ).execute())
            values = [float(v or 0) for v in (response.get("rows") or [[0] * 7])[0]]
        return Baseline(video, topic, *values)
