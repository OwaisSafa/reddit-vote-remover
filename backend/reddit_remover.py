import re
import time
from enum import Enum
from typing import Callable, Dict, Optional, Set

import requests


class VoteType(Enum):
    UPVOTED = "upvoted"
    DOWNVOTED = "downvoted"


class VoteState(Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"


ProgressCallback = Callable[[str, str, Optional[Dict]], None]


class RedditVoteRemover:
    POST_ID_PATTERN = re.compile(r'(?:id|post-id|data-ks-id)="(t3_[a-z0-9]+)"', re.I)
    AFTER_PATTERN = re.compile(r'(?:after=|"after":\s*")([^"&]+)', re.I)
    BASE_URL = "https://www.reddit.com"

    def __init__(self, cookies: str, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.graphql_url = f"{self.BASE_URL}/svc/shreddit/graphql"
        self._configure_session()
        self._set_cookies(cookies)
        self.csrf_token = self.session.cookies.get("csrf_token")

    def _configure_session(self):
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
            }
        )

    def _set_cookies(self, cookie_string: str):
        for cookie in cookie_string.split(";"):
            if "=" not in cookie:
                continue
            key, value = cookie.strip().split("=", 1)
            self.session.cookies.set(key.strip(), value.strip(), domain=".reddit.com")

    @staticmethod
    def _send_progress(
        callback: Optional[ProgressCallback],
        message: str,
        status: str = "info",
        stats: Optional[Dict] = None,
    ):
        if not callback:
            return
        try:
            callback(message, status, stats or {})
        except Exception:
            pass

    def _vote(self, post_id: str, vote_state: VoteState) -> bool:
        if not self.csrf_token:
            return False

        payload = {
            "operation": "UpdatePostVoteState",
            "variables": {"input": {"postId": post_id, "voteState": vote_state.value}},
            "csrf_token": self.csrf_token,
        }

        try:
            response = self.session.post(self.graphql_url, json=payload, timeout=10)
            result = response.json()
            return (
                result.get("data", {})
                .get("updatePostVoteState", {})
                .get("ok", False)
            )
        except Exception:
            return False

    def _get_voted_posts(
        self, username: str, vote_type: VoteType, debug: bool = False
    ) -> Set[str]:
        all_post_ids: Set[str] = set()
        voted_url = f"{self.BASE_URL}/user/{username}/{vote_type.value}/"
        after = None
        page = 1

        original_accept = self.session.headers.get("Accept")
        self.session.headers[
            "Accept"
        ] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

        try:
            while True:
                url = (
                    f"{self.BASE_URL}/svc/shreddit/profiles/profile_{vote_type.value}-more-posts/new/"
                    if after
                    else voted_url
                )
                params = {"after": after, "name": username} if after else None

                response = self.session.get(url, params=params, timeout=10)

                if response.status_code == 404:
                    if debug:
                        print(
                            f"\n✗ Cannot access {vote_type.value} page. "
                            "Ensure it is public in Reddit settings."
                        )
                    return set()

                response.raise_for_status()
                html = response.text

                post_ids = set(self.POST_ID_PATTERN.findall(html))
                all_post_ids.update(post_ids)

                if debug:
                    print(
                        f"Page {page}: +{len(post_ids)} posts (Total: {len(all_post_ids)})"
                    )

                after_matches = self.AFTER_PATTERN.findall(html)
                next_after = (
                    after_matches[0].replace("%3D", "=") if after_matches else None
                )

                if not next_after or next_after == after or not post_ids:
                    break

                after = next_after
                page += 1
                time.sleep(0.3)

            return all_post_ids

        except Exception as exc:
            if debug:
                print(f"✗ Error: {exc}")
            return all_post_ids

        finally:
            if original_accept:
                self.session.headers["Accept"] = original_accept

    def remove_votes(
        self,
        username: str,
        vote_type: VoteType,
        delay: float = 0.5,
        debug: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, int]:
        vote_state = VoteState.UP if vote_type == VoteType.UPVOTED else VoteState.DOWN
        stats = {"total": 0, "removed": 0, "failed": 0}

        if debug:
            print(f"\n{'=' * 50}\nRemoving {vote_type.value}...")

        post_ids = self._get_voted_posts(username, vote_type, debug)
        stats["total"] = len(post_ids)

        if not post_ids:
            self._send_progress(
                progress_callback,
                f"No {vote_type.value} posts found for @{username}.",
                "warning",
                stats.copy(),
            )
            return stats

        self._send_progress(
            progress_callback,
            f"Processing {len(post_ids)} {vote_type.value} posts...",
            "info",
            stats.copy(),
        )

        if debug:
            print(f"\nProcessing {len(post_ids)} posts...\n")

        post_url_map = {}
        try:
            html = None
            if post_ids and username and vote_type:
                voted_url = f"{self.BASE_URL}/user/{username}/{vote_type.value}/"
                first_html_resp = self.session.get(voted_url, timeout=10)
                if first_html_resp.status_code == 200:
                    html = first_html_resp.text
                    for post_id in post_ids:
                        post_id_short = post_id[3:]
                        pattern = re.compile(
                            r'<a[^>]*href=["\'](/r/[^/]+/comments/[^"\']*' + re.escape(post_id_short) + r'[^"\']*)["\'][^>]*>',
                            re.I
                        )
                        for match in pattern.finditer(html):
                            sub_url = match.group(1)
                            if sub_url.startswith('/'):
                                sub_url = f"https://www.reddit.com{sub_url}"
                            post_url_map[post_id] = sub_url
                            break
        except Exception:
            pass

        for i, post_id in enumerate(post_ids, 1):
            self._vote(post_id, vote_state)
            time.sleep(0.3)

            if self._vote(post_id, VoteState.NONE):
                stats["removed"] += 1
                message = f"[{i}/{stats['total']}] ✓ {post_id}"
                success = True
            else:
                stats["failed"] += 1
                message = f"[{i}/{stats['total']}] ✗ {post_id}"
                success = False

            url = post_url_map.get(post_id, f"https://www.reddit.com/comments/{post_id[3:]}")
            if progress_callback:
                self._send_progress(
                    progress_callback,
                    message,
                    "success" if success else "error",
                    {**stats, "post_id": post_id, "url": url, "success": success},
                )

            if debug:
                print(message)

            if i < stats["total"]:
                time.sleep(max(0.3, delay))

        if debug:
            print(
                f"\n{'=' * 50}\nRemoved: {stats['removed']}/{stats['total']} | "
                f"Failed: {stats['failed']}\n"
            )

        self._send_progress(
            progress_callback,
            f"Finished {vote_type.value} removal.",
            "success",
            stats.copy(),
        )
        return stats

