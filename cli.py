"""
Reddit Bulk Vote Remover - Simplified & Optimized
"""

import requests
import re
import time
from typing import Optional, List, Dict
from enum import Enum


class VoteType(Enum):
    UPVOTED = "upvoted"
    DOWNVOTED = "downvoted"


class VoteState(Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"


class RedditVoteRemover:
    """Optimized class to bulk remove Reddit votes."""

    # Compile regex patterns once for performance
    POST_ID_PATTERN = re.compile(r'(?:id|post-id|data-ks-id)="(t3_[a-z0-9]+)"', re.I)
    AFTER_PATTERN = re.compile(r'(?:after=|"after":\s*")([^"&]+)', re.I)

    def __init__(self, cookies: str):
        self.session = requests.Session()
        self.base_url = "https://www.reddit.com"
        self.graphql_url = f"{self.base_url}/svc/shreddit/graphql"

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        })

        self._set_cookies(cookies)
        self.csrf_token = self.session.cookies.get('csrf_token')

    def _set_cookies(self, cookie_string: str):
        """Parse and set cookies from string."""
        for cookie in cookie_string.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                self.session.cookies.set(key.strip(), value.strip(), domain='.reddit.com')

    def _vote(self, post_id: str, vote_state: VoteState) -> bool:
        """Send vote request. Returns True if successful."""
        if not self.csrf_token:
            return False

        payload = {
            "operation": "UpdatePostVoteState",
            "variables": {"input": {"postId": post_id, "voteState": vote_state.value}},
            "csrf_token": self.csrf_token
        }

        try:
            response = self.session.post(self.graphql_url, json=payload, timeout=10)
            result = response.json()
            return result.get("data", {}).get("updatePostVoteState", {}).get("ok", False)
        except:
            return False

    def _get_voted_posts(self, username: str, vote_type: VoteType, debug: bool = False) -> set:
        """Fetch voted post IDs. Returns a set for O(1) lookups."""
        all_post_ids = set()
        voted_url = f"{self.base_url}/user/{username}/{vote_type.value}/"
        after = None
        page = 1

        # Cache original accept header
        original_accept = self.session.headers.get("Accept")
        self.session.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

        try:
            while True:
                url = (f"{self.base_url}/svc/shreddit/profiles/profile_{vote_type.value}-more-posts/new/"
                       if after else voted_url)
                params = {"after": after, "name": username} if after else None

                response = self.session.get(url, params=params, timeout=10)

                if response.status_code == 404:
                    if debug:
                        print(f"\n✗ Cannot access {vote_type.value} page. Make sure it's public in Reddit settings.")
                    return set()

                response.raise_for_status()
                html = response.text

                # Use compiled regex pattern
                post_ids = set(self.POST_ID_PATTERN.findall(html))
                all_post_ids.update(post_ids)

                if debug:
                    print(f"Page {page}: +{len(post_ids)} posts (Total: {len(all_post_ids)})")

                # Check for next page
                after_matches = self.AFTER_PATTERN.findall(html)
                next_after = after_matches[0].replace('%3D', '=') if after_matches else None

                if not next_after or next_after == after or not post_ids:
                    break

                after = next_after
                page += 1
                time.sleep(0.3)

            return all_post_ids

        except Exception as e:
            if debug:
                print(f"✗ Error: {e}")
            return all_post_ids

        finally:
            if original_accept:
                self.session.headers["Accept"] = original_accept

    def remove_votes(self, username: str, vote_type: VoteType, delay: float = 0.5, debug: bool = False) -> Dict:
        """Remove all votes of specified type."""
        vote_state = VoteState.UP if vote_type == VoteType.UPVOTED else VoteState.DOWN

        if debug:
            print(f"\n{'='*50}\nRemoving {vote_type.value}...")

        post_ids = self._get_voted_posts(username, vote_type, debug)

        if not post_ids:
            return {"total": 0, "removed": 0, "failed": 0}

        if debug:
            print(f"\nProcessing {len(post_ids)} posts...\n")

        removed = failed = 0

        for i, post_id in enumerate(post_ids, 1):
            # Toggle vote then set to NONE
            self._vote(post_id, vote_state)
            time.sleep(0.3)

            if self._vote(post_id, VoteState.NONE):
                removed += 1
                if debug:
                    print(f"[{i}/{len(post_ids)}] ✓ {post_id}")
            else:
                failed += 1
                if debug:
                    print(f"[{i}/{len(post_ids)}] ✗ {post_id}")

            if i < len(post_ids):
                time.sleep(delay)

        if debug:
            print(f"\n{'='*50}\nRemoved: {removed}/{len(post_ids)} | Failed: {failed}\n")

        return {"total": len(post_ids), "removed": removed, "failed": failed}


def main():
    """Simplified interactive interface."""
    print("Reddit Bulk Vote Remover\n")

    # Get inputs
    cookies = input("Cookies: ").strip()
    if not cookies:
        print("✗ No cookies provided")
        return

    username = input("Username: ").strip().replace('u/', '')
    if not username:
        print("✗ No username provided")
        return

    print("\n1. Upvotes\n2. Downvotes\n3. Both")
    choice = input("Choice (1-3): ").strip()
    if choice not in ['1', '2', '3']:
        print("✗ Invalid choice")
        return

    delay_input = input("Delay (default 0.5s): ").strip()
    delay = float(delay_input) if delay_input and delay_input.replace('.','').isdigit() else 0.5
    delay = max(0.3, delay)

    print(f"\n⚠️  Remove {'upvotes' if choice=='1' else 'downvotes' if choice=='2' else 'all votes'} for @{username}?")
    if input("Type 'yes' to confirm: ").lower() != 'yes':
        print("✗ Cancelled")
        return

    # Execute
    try:
        remover = RedditVoteRemover(cookies)

        if choice in ['1', '3']:
            result = remover.remove_votes(username, VoteType.UPVOTED, delay, debug=True)

        if choice in ['2', '3']:
            result = remover.remove_votes(username, VoteType.DOWNVOTED, delay, debug=True)

        print("✓ Done!")

    except KeyboardInterrupt:
        print("\n✗ Interrupted")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    main()
