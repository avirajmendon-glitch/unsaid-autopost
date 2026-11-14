# unsaid-autopost

Publishes @unsaid.at.nine posts to Instagram on schedule.

- `posts.json`: the queue (times in UTC), `media/`: the JPEG images and MP4 reels.
- `.github/workflows/autopost.yml` runs `post.py` every 10 minutes; it posts anything due and records it in `posted.json`.
- Needs repo secret `IG_TOKEN` (`IG_USER_ID` optional) (Settings → Secrets and variables → Actions).
- To post one now: Actions → autopost → Run workflow, enter the post number.
