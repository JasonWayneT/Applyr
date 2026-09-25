---
name: networking-outreach
description: Draft a message for reaching out to someone connected to a target company, whether the hiring manager for the role or an unrelated-department contact (alum, former coworker, warm connection). Use when Jason names a specific person he found on LinkedIn or elsewhere and wants a message drafted, or asks "what should I say" / "how do I reach out" about a contact at a company he's applying to. Covers message sequencing, what actually moves an application forward versus what just feels like networking, and templates for both contact types.
license: private
---

Canonical copy for Codex and harnesses that load `.codex/skills/`.
Claude Code loads a pointer at `.claude/skills/networking-outreach/SKILL.md`.
Do not keep a second full copy under another harness directory.

# Networking Outreach

Research-backed playbook for outreach messages to people at target companies. Built 2026-07-30 after
drafting two rounds of a message to a CivicPlus contact that missed the mark twice: first too soft (asked
for "an honest take" with no concrete ask), then overcorrected to a cold hard ask with no relationship
framing. This skill exists so neither failure mode repeats.

## Three contact types, three different messages

The first thing to identify before drafting anything: **is there an open role, and is this person in the
hiring chain for it?**

- **Type A — Hiring-manager / role-relevant contact** (posted the JD, leads the team, is a recruiter for
  that req): they can evaluate fit directly. Lead with the role and 2-3 concrete fit reasons.
- **Type B — Unrelated-department warm connection** (alum, former coworker, warm connection who happens to
  work there but isn't hiring for this role): they cannot evaluate PM fit and shouldn't be asked to. Get
  their honest read AND make it easy for them to refer or point you to the right person.
- **Type C — Informational interview, no open role** (reaching out to build a relationship at a company
  *before* a role exists, or to someone whose work you admire regardless of current openings): this is
  the proactive-networking move, distinct from A and B because there's nothing to react to yet. See below.

Don't use the Type A "here's why I'm a fit" pitch on a Type B or C contact. It's the wrong pitch to the
wrong audience — a Technical Support Engineer can't assess your product-management background, and
pitching fit with no role on the table reads as job-hunting pressure, which is exactly what informational
interviews are supposed to avoid.

## Why Type C matters — this is the actual fix for "blind applications aren't working"

Reactive outreach (Types A and B) only fires once a JD is posted, which means it inherits the same
timing problem as cold applications: you're one of everyone else who saw the same posting. Type C flips
that — you build the relationship before there's a role to compete for, so when something opens (or a
referral becomes possible), you're not starting from zero.

- Ashby's platform data across 38 million applications: referrals are only about 1% of applications, but
  40% of referred candidates reach interview, versus a much lower rate for cold applicants. A single
  internal referral effectively skips ~200 other applicants.
  [hiration.com](https://www.hiration.com/blog/job-application-black-hole/)
- Guidance from career-search sources: aim for 2-3 outreach messages a day, spending the start of the
  week identifying 5-10 target companies and searching for people in adjacent roles.
  [careerenlightenment.com](https://careerenlightenment.com/networking-tactics-job-seekers-2026)
- Volume alone isn't the differentiator — the people you're reaching tend to already get 30-80 outreach
  messages a week, so personalization matters more than message count.
  [careerenlightenment.com](https://careerenlightenment.com/networking-tactics-job-seekers-2026)

**Caveat:** one source recommends spending roughly 60% of job-search time on networking versus 40% on
applications, but that figure is framed for early-career job seekers specifically — Jason is 7 YOE, so
treat the ratio as directional (networking should be a much bigger share than it currently is, not
necessarily exactly 60/40) rather than a target to hit precisely.

### Type C template

Elements, in order: name a mutual contact or shared context in the subject/opener if one exists, a
one-sentence self-intro (who you are, what you do), specific personalization (something real about their
work or path, not generic flattery), a concrete time-boxed ask (20-30 minutes), and low-pressure framing
that makes clear this isn't a veiled job pitch.
[iHire](https://www.ihire.com/resourcecenter/jobseeker/pages/how-to-request-an-informational-interview-6-templates),
[Forbes](https://www.forbes.com/sites/josephliu/2024/01/10/how-to-write-an-effective-informational-interview-request-email/)

> Hi [Name], [shared context / how you found them]. I'm a product manager exploring [specific
> area/industry] and came across your work on [specific, real detail about them]. Would you have 20
> minutes sometime in the next couple weeks to talk about your path there and what you're seeing in the
> space? No agenda beyond learning, happy to work around your schedule.

Keep it under 150 words total. If the call happens, come with 5-7 real questions (career path, what a
typical week looks like, what's actually valued in the role you're aiming at, what they wish they'd known
earlier) — not a disguised pitch session.

## Core principle: relationship before ask, but don't bury the actual ask

The single most consistent finding across sources: leading with the ask before establishing any context
reads as transactional and gets ignored. One source compares an immediate referral request to "proposing
marriage on a first date." [linkedin.com/posts/colinlernell](https://www.linkedin.com/posts/colinlernell_a-cold-dm-wont-get-you-hired-networking-activity-7358612114091003904-Vnhh)

But the opposite failure is just as real and is the one this project hit first: a message that's *all*
relationship and never asks for anything concrete doesn't move anything forward either. "I'd love your
honest take" is a nice conversation starter that produces, at best, color commentary. It does not put you
in front of a hiring manager or get your name into an ATS as a referral. If the goal is advancing the
application (not just information), the message needs to sequence past the rapport line into a specific,
answerable ask in the same message. Job-search outreach at the volume Applyr operates at (many companies,
limited time per contact) can't afford genuine multi-week relationship-building with every warm lead — the
single-message version below compresses the sequencing into one send.

## Why referral is the actual lever, not just niceness

Numbers worth knowing so the ask doesn't get soft-pedaled out of politeness:

- Referred candidates get roughly **5x more interviews** than cold applicants, and are hired **about 55%
  faster**. [careery.pro](https://careery.pro/blog/networking/how-to-get-referred-for-a-job)
- Warm outreach reply rates run **10-34%**, versus a **2-5%** cold baseline, and can reach **40-50%** when
  a real referral or shared connection is involved.
  [overloop.com](https://overloop.com/blog/linkedin-outreach-benchmarks),
  [scayul.com](https://scayul.com/blog/the-death-of-cold-outreach-why-warm-introductions-convert-better-1)
- Cold connection-note reply rates are actively declining: 3.5% in May 2025 down to 2.2% by April 2026, a
  37% relative drop in one year. [overloop.com](https://overloop.com/blog/linkedin-outreach-benchmarks)

**Source-quality caveat:** the outreach-benchmark figures above come from recruiting/sales-tooling
marketing blogs (Overloop, Prospeo, Recruiterflow), not peer-reviewed studies — treat the exact percentages
as directional, not precise. The qualitative pattern (warm beats cold, referral beats no-referral, by a
lot) is corroborated across independent sources and is the safe part to act on. The exact numbers are not
something to quote to a contact or cite as fact anywhere outside this internal reasoning.

Referral works regardless of whether the contact is in the hiring department, because most companies route
referrals company-wide through an internal portal or recruiter forward, often with a referral bonus that
makes employees receptive even for a role outside their team.

## What to avoid

| Mistake | Why it fails | Fix |
|---|---|---|
| Generic "can you refer me to anything?" | Forces them to do the research for you | Name the specific role/title |
| Referral ask with zero relationship framing | Reads as transactional, first message | Open with the shared context (how you know of them) before the ask |
| Vague ask ("pick your brain," "would love your take") | No concrete action for them to take, and doesn't advance the application | Specific, answerable ask with an easy yes/no shape |
| No role link or resume offered | Makes it work for them to help you | Offer to send the job link/resume in the same message |
| Type A fit-pitch sent to a Type B contact | Wrong pitch for someone who can't evaluate it | Match the message to what this person can actually do for you |

## Type A — Hiring-manager / role-relevant contact

Already validated in this project (Principal Financial Group, 2026-07-22; see
`[[feedback_applyr_hiring_manager_outreach]]` in memory). Structure:

> I saw the [role] and thought it might be a good fit because [X, Y, Z]. Would love to connect about it.

- Lead with having seen the specific role, give 2-3 concrete fit reasons, close with a low-pressure
  connect ask.
- Casual/human register, contractions, no "I hope this message finds you well."
- Subject line (if used): name the specific team/product area, not "Applied to your role."
- 3-4 sentences max.

## Type B — Warm/unrelated-department contact (alum, former coworker)

Single-message template, sequenced correctly in one send rather than spread across a multi-touch drip:

> Hi [Name], fellow [shared context] here! I just applied for the [specific role] at [Company]. Would
> love a quick, honest read on what it's like there if you have a few minutes, and if it makes sense,
> whether you'd be comfortable pointing me toward whoever's running that search or putting in a referral.
> Happy to send more detail if useful.

Sequencing inside that one message, in order:
1. **Shared context first** ("fellow Cision alum") — this is the relationship anchor, even for someone
   never met directly. It's the reason the message isn't cold.
2. **Name the specific role** — never "any roles," always the actual title.
3. **Genuine question** ("what it's like there") before the ask — this is what keeps it from reading as
   transactional even inside a single message.
4. **Concrete, answerable ask** — referral or pointing to the right person, not "thoughts?" Give them a
   yes/no shape, not an open-ended favor.
5. **Easy exit ramp + offer to make it easy for them** ("happy to send more detail," "no pressure") — lowers
   the cost of saying yes and signals you won't chase them for materials later.

If Jason already knows the contact personally (actual prior working relationship, not just a shared former
employer), open with an actual reconnection line referencing that relationship instead of "fellow alum" —
confirm which situation it is before drafting, since the two need different openers.

## Timing and follow-up

- Wait at least 48 hours before any follow-up on an initial message or connection request.
- If no response, one follow-up after 5-7 days, ideally adding something new (an update, a specific
  question) rather than "just checking in."
- Cap at two follow-ups total, about a week apart. Beyond that, stop — don't risk the relationship for a
  job-search email.
- If they help in any way (intro, referral, advice), close the loop afterward with a thank-you and a
  status update once there's news. This is what makes a one-time favor into someone worth reaching out to
  again next search.

## Logging outreach in Applyr (CR-071)

After drafting a message (Type A, B, or C) and Jason has a version he's happy with, log it as a
`contacts` row via the Applyr API so the networking dashboard has something to show. This is a stub, not
a confirmation that the message was actually sent — see "Confirming the send" below for that step.

Requires the Applyr dev server running locally (`npm run dev` from the repo root, listening on
`http://localhost:3000`). If it's not running, tell Jason and skip logging rather than failing silently —
don't block finishing the draft on this.

```bash
curl -s -X POST http://localhost:3000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "company": "<company name>",
    "contact_name": "<contact name>",
    "contact_title": "<title, if known>",
    "contact_type": "<hiring_manager | warm_connection | informational>",
    "source": "<LinkedIn alum | mutual connection | cold search | etc, if known>",
    "job_id": "<job id, only if this outreach is tied to a specific open role Jason is tracking>",
    "message_sent_at": "<today, ISO date>",
    "next_follow_up_due": "<today + 2 days, ISO date>",
    "status": "active",
    "confirmed": false
  }'
```

Field mapping:
- `contact_type`: Type A → `hiring_manager`, Type B → `warm_connection`, Type C → `informational`.
- `job_id`: only set when the conversation has a specific tracked role in scope (Type A, and Type B when
  it's tied to an actual posted role). Type C and any Type B contact met before a role exists have no
  `job_id` — leave it out entirely rather than guessing one. If unsure whether a job is in scope, ask
  Jason rather than assume.
- `next_follow_up_due`: today + 48 hours (the "Timing and follow-up" section's own first-follow-up
  window above) — this is what feeds the Needs Attention card's Follow-up Due group, not a hard deadline.
- Leave `contact_title` / `source` out of the payload if not known — don't guess.

The response's `contact.id` is the row's id — hold onto it in the conversation, it's needed for the
confirm step below.

## Confirming the send

The stub above is written at draft time, before Jason has actually sent anything. Don't flip `confirmed`
automatically — ask him directly, in the same session, once he'd plausibly have sent it ("sent that one?"
or similar, whenever it naturally comes up next in the conversation). This is deliberately not a
browser-tap-to-confirm flow — the skill runs inside a coding-agent session with tool access regardless of
whether Jason has Applyr open in a tab, so asking directly is the more reliable path than depending on him
being in the UI at the right moment.

If he confirms it was sent:

```bash
curl -s -X PATCH http://localhost:3000/api/contacts/<contact_id> \
  -H "Content-Type: application/json" \
  -d '{"confirmed": true, "log_touch": true}'
```

`log_touch: true` bumps `last_touch_at` to reflect the real send time rather than the stub's creation
time. If he says it wasn't sent (plans changed, rewrote it elsewhere, etc.), leave `confirmed: false` —
don't chase a status on it, the row just sits as an unconfirmed stub.

## Forbidden language

Same anti-AI-fingerprint rules as `CoverLetter.md` apply here even though nothing lints these messages —
see `CLAUDE.md`'s "Forbidden Language" section and `[[feedback_applyr_app_question_style]]` in memory. No
em dashes, no semicolons, no "leverage/passionate/driven/dynamic/innovative," no "I hope this message
finds you well" or other throat-clearing.

## Sources

- [LinkedIn — cold DM won't get you hired](https://www.linkedin.com/posts/colinlernell_a-cold-dm-wont-get-you-hired-networking-activity-7358612114091003904-Vnhh)
- [LinkedIn outreach tips for job seekers](https://www.linkedin.com/top-content/career/job-market-navigation-tips/linkedin-outreach-tips-for-job-seekers/)
- [Forbes — 3 things not to say when you want a referral](https://www.forbes.com/sites/shodewan/2025/07/16/3-things-not-to-say-when-you-want-a-referral-say-this-instead/)
- [How to ask a connection for another referral](https://www.linkedin.com/top-content/career/career-advancement-tips/how-to-ask-a-connection-for-another-referral/)
- [refer.me — how to ask for a referral on LinkedIn](https://www.refer.me/blog/how-to-ask-for-a-referral-on-linkedin-with-templates)
- [LinkedIn — 3 cold messages that actually got responses](https://www.linkedin.com/posts/adamrbroda_3-cold-messages-that-actually-got-responses-activity-7331304389900386304-6tpC)
- [Overloop — LinkedIn outreach benchmarks 2026](https://overloop.com/blog/linkedin-outreach-benchmarks)
- [Careery.pro — how to get referred for a job](https://careery.pro/blog/networking/how-to-get-referred-for-a-job)
- [Scayul — the death of cold outreach](https://scayul.com/blog/the-death-of-cold-outreach-why-warm-introductions-convert-better-1)
- [RequestLetters — how to ask for a job referral on LinkedIn without sounding pushy](https://requestletters.com/home/how-to-ask-for-a-job-referral-on-linkedin-without-sounding-pushy)
