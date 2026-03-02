# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Proxy / Network Access Notes

- `proxychains4` is installed: `/usr/bin/proxychains4`
- Active config file: `/etc/proxychains.conf`
- Current proxy route:
  - `strict_chain`
  - `proxy_dns`
  - `socks5 127.0.0.1 7891`
- Practical usage:
  - Direct `x.com` may return anti-bot / 403 in CLI mode.
  - For tweet content extraction, prefer `fxtwitter.com` mirror with proxy:
    - `proxychains4 -q curl -sS -L "https://fxtwitter.com/<user>/status/<id>"`
  - The tweet body can often be read from `og:description` in returned HTML.

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
