from yt_idea_collector.youtube import YouTubeClient, parse_duration


def test_parse_duration():
    assert parse_duration("PT12M5S") == 725
    assert parse_duration("PT1H2M3S") == 3723
    assert parse_duration("P1DT1S") == 86401


def test_invalid_duration_is_safe():
    assert parse_duration("not-a-duration") == 0


class Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class Resource:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return Request(self.responses.pop(0))


class DataAPI:
    def __init__(self, thread_pages, reply_pages):
        self.threads = Resource(thread_pages)
        self.reply_resource = Resource(reply_pages)

    def commentThreads(self):
        return self.threads

    def comments(self):
        return self.reply_resource


def comment_resource(comment_id, video_id="v1"):
    return {"id": comment_id, "snippet": {
        "videoId": video_id, "authorDisplayName": "Viewer",
        "authorChannelId": {"value": "viewer-channel"}, "textOriginal": "Try this",
        "publishedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
        "likeCount": 1,
    }}


def test_comment_pages_and_incomplete_replies_are_fully_fetched():
    top1, top2 = comment_resource("top1"), comment_resource("top2")
    embedded = comment_resource("reply1")
    full_reply = comment_resource("reply2")
    pages = [
        {"items": [{"snippet": {"topLevelComment": top1, "totalReplyCount": 2},
                     "replies": {"comments": [embedded]}}], "nextPageToken": "next"},
        {"items": [{"snippet": {"topLevelComment": top2, "totalReplyCount": 0}}]},
    ]
    data = DataAPI(pages, [{"items": [embedded, full_reply]}])
    comments = YouTubeClient(data, None, "owner").list_comments()
    assert [comment.id for comment in comments] == ["top1", "reply1", "reply2", "top2"]
    assert len(data.threads.calls) == 2
    assert data.reply_resource.calls[0]["parentId"] == "top1"
